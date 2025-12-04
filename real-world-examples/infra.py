# infra.py -- simplified infrastructure library

# libraries
import os, time
import boto3
from pprint import pprint

# global variables
ec2 = boto3.client(
    "ec2",
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    region_name=os.environ["AWS_REGION"],
)

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    region_name=os.environ["AWS_REGION"],
)


# functions
def list_instances(name=None, instance_id=None):
    response = ec2.describe_instances()
    assert (
        response["ResponseMetadata"]["HTTPStatusCode"] == 200
    ), f"Error in describe_instances() response: {response}."
    assert "Reservations" in response, "Response missing 'Reservations' information."
    for r in response["Reservations"]:
        assert len(r["Instances"]) == 1, "Wrong number of reservations in instance."
    results = [r["Instances"][0] for r in response["Reservations"]]
    instances = []
    for result in results:
        instance = {
            "image_id": result["ImageId"],
            "instance_id": result["InstanceId"],
            "instance_type": result["InstanceType"],
            "key_name": result.get("KeyName", "-"),
            "launch_time": result["LaunchTime"],
            "state": result["State"]["Name"],
            "zone": result["Placement"]["AvailabilityZone"],
        }
        instance_name = "-"
        if "Tags" in result:
            for tag in result["Tags"]:
                if "Key" in tag:
                    instance_name = tag["Value"]
        instance["name"] = instance_name
        if (len(result["NetworkInterfaces"]) > 0) and (
            "Association" in result["NetworkInterfaces"][0]
        ):
            instance["public_ip"] = result["NetworkInterfaces"][0]["Association"][
                "PublicIp"
            ]
            instance["public_dns_name"] = result["NetworkInterfaces"][0]["Association"][
                "PublicDnsName"
            ]
        else:
            instance["public_ip"] = "-"
            instance["public_dns_name"] = "-"
        instance["security_group_name"] = ",".join(
            [g["GroupName"] for g in result["SecurityGroups"]]
        )
        instance["security_group_id"] = ",".join(
            [g["GroupId"] for g in result["SecurityGroups"]]
        )
        instance["volumes"] = []
        for mapping in result["BlockDeviceMappings"]:
            volume = {
                "name": mapping["DeviceName"],
                "delete_on_termination": mapping["Ebs"]["DeleteOnTermination"],
                "status": mapping["Ebs"]["Status"],
                "volume_id": mapping["Ebs"]["VolumeId"],
            }
            instance["volumes"].append(volume)
        r = ec2.describe_instance_attribute(
            Attribute="disableApiTermination", InstanceId=result["InstanceId"]
        )
        instance["termination_protection"] = r["DisableApiTermination"]["Value"]
        r = ec2.describe_instance_status(InstanceIds=[result["InstanceId"]])
        instance_statuses = r["InstanceStatuses"]
        if len(instance_statuses) > 0:
            instance["instance_status"] = instance_statuses[0]["InstanceStatus"][
                "Status"
            ]
            instance["system_status"] = instance_statuses[0]["SystemStatus"]["Status"]
        else:
            instance["instance_status"] = "-"
            instance["system_status"] = "-"
        instances.append(instance)
    if name:
        instances = [i for i in instances if i["name"] == name]
    if instance_id:
        instances = [i for i in instances if i["instance_id"] == instance_id]
    return instances


def list_instance(name=None, instance_id=None):
    assert type(name) is str or type(instance_id) is str
    instances = list_instances(name=name, instance_id=instance_id)
    assert len(instances) > 0, f"Instance {name} does not exist."
    assert (
        len(instances) == 1
    ), f"Instance specifies more than one instance. (N={len(instances)})"
    return instances[0]


def list_volumes(volume_id=None):
    response = ec2.describe_volumes()
    assert (
        response["ResponseMetadata"]["HTTPStatusCode"] == 200
    ), f"Error in describe_volumes() response: {response}"
    assert "Volumes" in response, "Response missing 'Volumes' information."
    results = response["Volumes"]
    volumes = []
    for result in results:
        volume = {
            "volume_id": result["VolumeId"],
            "type": result["VolumeType"],
            "size": result.get("Size"),
            "create_time": result["CreateTime"],
            "state": result["State"],
            "zone": result["AvailabilityZone"],
            "encrypted": result["Encrypted"],
        }
        volume["name"] = "-"
        if "Tags" in result:
            for tag in result["Tags"]:
                if "Key" in tag:
                    volume["name"] = tag["Value"]
        volume["attachments"] = []
        for item in result["Attachments"]:
            volume["attachments"].append(
                {
                    "instance_id": item["InstanceId"],
                    "device": item["Device"],
                    "state": item["State"],
                }
            )
        volumes.append(volume)
    if volume_id:
        volumes = [v for v in volumes if v["volume_id"] == volume_id]
    return volumes


def list_volume(volume_id=None):
    assert type(volume_id) is str
    volumes = list_volumes(volume_id=volume_id)
    assert (
        len(volumes) == 1
    ), f"Volume does not exist or specifies more than one volume. (N={len(volumes)})"
    return volumes[0]


def set_termination_protection(instance_id, value):
    # verify that the name goes with the instance ID
    instances = list_instances(instance_id=instance_id)
    assert len(instances) == 1, f"Instance {instance_id} not found."
    instance = instances[0]
    print(
        f"Setting termination_protection for {instance_id}/{instance['name']} to {value}."
    )
    response = ec2.modify_instance_attribute(
        DisableApiTermination={"Value": value}, InstanceId=instance_id
    )
    assert (
        response["ResponseMetadata"]["HTTPStatusCode"] == 200
    ), f"Error in modify_instance_attribute() response: {response}"
    response = ec2.describe_instance_attribute(
        Attribute="disableApiTermination", InstanceId=instance["instance_id"]
    )
    assert response["DisableApiTermination"]["Value"] == value
    return


def create_instance(
    name,
    instance_type="t2.micro",
    image_id="ami-097a2df4ac947655f",
    zone="us-east-2c",
    key_name=None,
    security_group_id="sg-0364d234122df6a66",
    device="/dev/sda1",
    disk_size=0,
    delete_on_termination=True,
    termination_protection=True,
):
    # make sure the instance with that name doesn't exist
    assert len(list_instances(name)) == 0, f"Instance '{name}' already exists."
    print(f"Creating instance {name}.")
    assert type(name) is str and len(name) > 2, f"Illegal instance name {[str]}."
    assert disk_size > 0, f"Disk_size={disk_size} is too small."
    assert key_name, f"Key name (key_name) argument must be provided."
    response = ec2.run_instances(
        BlockDeviceMappings=[
            {
                "DeviceName": device,
                "Ebs": {
                    "DeleteOnTermination": delete_on_termination,
                    "VolumeSize": disk_size,
                    "VolumeType": "gp2",
                },
            }
        ],
        ImageId=image_id,
        InstanceType=instance_type,
        MaxCount=1,
        MinCount=1,
        Monitoring={"Enabled": False},
        Placement={"AvailabilityZone": zone},
        KeyName=key_name,
        SecurityGroupIds=[security_group_id],
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": name}],
            }
        ],
    )
    assert (
        response["ResponseMetadata"]["HTTPStatusCode"] == 200
    ), f"Error in run_instances() response: {response}"
    instance = None
    instance_state = "unknown"
    for i in range(1, 120):
        time.sleep(1)
        if i % 5 == 0:
            instance = list_instance(name=name)
            instance_id = instance["instance_id"]
            instance_state = instance["state"]
            if instance_state == "running":
                break
            print(f"Waiting on start of instance {instance_id}/{name}. ({i} sec)")

    if instance_state != "running":
        raise Exception(f"Instance {name} did not start {instance}.")

    # set the termination protection
    set_termination_protection(instance_id, termination_protection)

    # make sure the instance was created correctly
    instance = list_instance(instance_id=instance_id)

    # check some things about the instance
    assert instance["name"] == name
    assert instance["instance_id"] == instance_id
    assert instance["state"] == "running"
    assert instance["instance_type"] == instance_type
    assert instance["image_id"] == "ami-097a2df4ac947655f"
    assert instance["key_name"] == key_name
    assert instance["security_group_id"] == "sg-0364d234122df6a66"
    assert instance["termination_protection"] == termination_protection
    assert instance["instance_status"] == "initializing"
    assert instance["system_status"] == "initializing"
    instance_id = instance["instance_id"]

    # check storage
    volumes = instance["volumes"]
    assert len(volumes) == 1
    assert volumes[0]["delete_on_termination"] == True
    assert volumes[0]["status"] == "attached"
    volume_id = volumes[0]["volume_id"]
    assert volume_id.startswith("vol-")
    assert volumes[0]["name"] == device

    # verify the volume info
    volume = list_volumes(volume_id=volume_id)[0]
    assert volume["volume_id"] == volume_id
    assert volume["size"] == disk_size
    assert volume["type"] == "gp2"
    assert len(volume["attachments"]) == 1
    assert volume["attachments"][0]["instance_id"] == instance_id
    assert volume["attachments"][0]["device"] == device
    print(f"Instance {name} was created.")

    return instance


def terminate_instance(instance_id):
    # verify that the name goes with the instance ID
    instance = list_instance(instance_id=instance_id)
    volumes = instance["volumes"]
    print(f"Terminating instance {instance_id}/{instance['name']}.")
    response = ec2.terminate_instances(InstanceIds=[instance_id])
    try:
        assert (
            response["ResponseMetadata"]["HTTPStatusCode"] == 200
        ), f"Error in terminate_instances() response: {response}"
    except Exception as e:
        print("raising error in termination.")
        raise (e)
    instance_state = "unknown"
    for i in range(1, 180):
        time.sleep(1)
        if i % 5 == 0:
            instance = list_instance(instance_id=instance_id)
            instance_state = instance["state"]
            if instance_state == "terminated":
                break
            print(
                f"Waiting on termination of instance {instance_id}/{instance['name']}. ({i} sec)"
            )
    if instance_state != "terminated":
        raise Exception(f"Instance {instance_id} did not terminate: {instance}")

    # verify that the volumes ae gone
    for volume in volumes:  # here was are going over the -old- instance volume list
        if volume["delete_on_termination"]:
            assert (
                len(list_volumes(volume_id=volume["volume_id"])) == 0
            ), f"Volume {volume_id} not deleted: {volume}"
            print(f"Volume {volume['volume_id']} was deleted at instance termination.")
        else:
            print(
                f"Volume {volume['volume_id']} was not marked for 'delete_on_termination'."
            )
    return instance


def list_buckets(name=None):
    response = s3.list_buckets()
    assert (
        response["ResponseMetadata"]["HTTPStatusCode"] == 200
    ), f"Error in list_buckets() response: {response}"
    assert "Buckets" in response, "Response missing 'Buckets' information."
    buckets = [
        {"name": b["Name"], "creation_date": b["CreationDate"]}
        for b in response["Buckets"]
    ]
    if name:
        buckets = [b for b in buckets if b["name"] == name]
    for b in buckets:
        # get encryption
        try:
            response = s3.get_bucket_encryption(Bucket=b["name"])
            assert (
                response["ResponseMetadata"]["HTTPStatusCode"] == 200
            ), f"Error in get_bucket_encryption() response: {response}"
            response = response["ServerSideEncryptionConfiguration"]["Rules"][0]
            response = response["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"]
            b["encryption"] = response
        except Exception as e:
            error = str(e)
            if "not found" in error:
                b["encryption"] = "Not Found"
            else:
                b["encryption"] = "Error" + str(e)

        # get versioning
        try:
            response = s3.get_bucket_versioning(Bucket=b["name"])
            assert (
                response["ResponseMetadata"]["HTTPStatusCode"] == 200
            ), f"Error in get_bucket_versioning() response: {response}"
            b["versioning"] = response["Status"]
        except Exception as e:
            if str(e) == "'Status'":
                b["versioning"] = "Not Found"
            else:
                b["versioning"] = "Error:" + str(e)

        # get public access blocking status
        try:
            response = s3.get_public_access_block(Bucket=b["name"])
            assert (
                response["ResponseMetadata"]["HTTPStatusCode"] == 200
            ), f"Error in get_public_access_block() response: {response}"
            b["public_access_blocked"] = "Blocked"
            for key in [
                "BlockPublicAcls",
                "BlockPublicPolicy",
                "IgnorePublicAcls",
                "RestrictPublicBuckets",
            ]:
                if response["PublicAccessBlockConfiguration"][key] != True:
                    b["public_access_blocked"] = "Not Blocked"
        except Exception as e:
            error = str(e)
            if "not found" in error:
                b["public_access_blocked"] = "Not Found"
            else:
                b["public_access_blocked"] = "Error:" + str(e)

        try:
            response = s3.get_bucket_cors(Bucket=b["name"])
            assert (
                response["ResponseMetadata"]["HTTPStatusCode"] == 200
            ), f"Error in get_bucket_cors() response: {response}"
            cors_rules = response["CORSRules"][0]
            assert cors_rules["AllowedHeaders"] == ["*"]
            assert cors_rules["AllowedMethods"] == ["GET"]
            b["cors_allowed_origins"] = cors_rules["AllowedOrigins"]
        except Exception as e:
            error = str(e)
            if "does not exist" in error:
                b["cors_allowed_origins"] = []
            else:
                b["cors_allowed_origins"] = "Error:" + str(e)
    return buckets


def list_bucket(name=None):
    assert type(name) is str
    buckets = list_buckets(name=name)
    assert (
        len(buckets) == 1
    ), f"Bucket does not exist or specifies more than one bucket. (N={len(buckets)})"
    return buckets[0]


def delete_bucket(name=None):
    assert type(name) is str
    response = s3.delete_bucket(Bucket=name)
    assert response["ResponseMetadata"]["HTTPStatusCode"] in [
        200,
        204,
    ], f"Error in delete_bucket() response: {response}"


def create_bucket(name=None, cors_allowed_origins=[]):
    assert type(name) is str
    assert type(cors_allowed_origins) is list
    for item in cors_allowed_origins:
        assert type(item) is str

    # Create the bucket in the default region
    response = s3.create_bucket(
        Bucket=name,
        CreateBucketConfiguration={"LocationConstraint": os.environ["AWS_REGION"]},
    )
    assert response["ResponseMetadata"]["HTTPStatusCode"] in [
        200,
        204,
    ], f"Error in create_bucket() response: {response}"

    response = s3.put_bucket_encryption(
        Bucket=name,
        ServerSideEncryptionConfiguration={
            "Rules": [
                {
                    "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"},
                }
            ]
        },
    )
    assert response["ResponseMetadata"]["HTTPStatusCode"] in [
        200,
        204,
    ], f"Error in put_bucket_encryption() response: {response}"

    response = s3.put_bucket_versioning(
        Bucket=name, VersioningConfiguration={"Status": "Enabled"}
    )
    assert response["ResponseMetadata"]["HTTPStatusCode"] in [
        200,
        204,
    ], f"Error in put_bucket_versioning() response: {response}"

    response = s3.put_public_access_block(
        Bucket=name,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    assert response["ResponseMetadata"]["HTTPStatusCode"] in [
        200,
        204,
    ], f"Error in put_public_access_block() response: {response}"

    response = s3.put_bucket_cors(
        Bucket=name,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedHeaders": ["*"],
                    "AllowedMethods": ["GET"],
                    "AllowedOrigins": cors_allowed_origins,
                }
            ]
        },
    )
    assert response["ResponseMetadata"]["HTTPStatusCode"] in [
        200,
        204,
    ], f"Error in put_bucket_cors() response: {response}"

    # Check if the bucket was successfully created
    bucket = list_bucket(name=name)

    # return the bucket information
    return bucket


# test libraries
import datetime, random
from pprint import pprint
import botocore.client


# test functions
def test_initialization():
    print("test_initializion")
    # Below, normal class assertion (e,g "is botocore.client.EC2") doesn't work
    # See https://stackoverflow.com/questions/72221091/im-trying-to-type-annotate-around-boto3-but-module-botocore-client-has-no-at
    assert str(type(ec2)) == "<class 'botocore.client.EC2'>"


def test_list_instances():
    print("test_list_instances")
    instances = list_instances()
    assert type(instances) is list
    assert len(instances) > 0
    for instance in instances:
        assert type(instance) is dict
        for key in [
            "image_id",
            "instance_id",
            "instance_type",
            "key_name",
            "launch_time",
            "state",
            "zone",
            "public_ip",
            "public_dns_name",
            "name",
            "security_group_name",
            "security_group_id",
            "volumes",
        ]:
            assert key in instance
        for key in ["volumes"]:
            assert type(instance[key]) is list
        for key in ["launch_time"]:
            assert type(instance[key]) is datetime.datetime
        for key in [
            "image_id",
            "instance_id",
            "instance_type",
            "key_name",
            "state",
            "zone",
            "public_ip",
            "public_dns_name",
            "name",
            "security_group_name",
            "security_group_id",
            "instance_status",
            "system_status",
        ]:
            assert type(instance[key]) is str
        assert instance["termination_protection"] in [True, False]
    random_instance = instances[3]
    random_token = str(random.randint(10000000, 99999999))
    instances = list_instances(name=random_token)
    assert len(instances) == 0
    instances = list_instances(name=random_instance["name"])
    assert len(instances) == 1
    assert instances[0]["name"] == random_instance["name"]
    instances = list_instances(instance_id=random_token)
    assert len(instances) == 0
    instances = list_instances(instance_id=random_instance["instance_id"])
    assert len(instances) == 1
    assert instances[0]["instance_id"] == random_instance["instance_id"]


def test_list_volumes():
    print("test_list_volumes")
    volumes = list_volumes()
    assert type(volumes) is list
    assert len(volumes) > 0
    for volume in volumes:
        assert type(volume) is dict
        for key in [
            "attachments",
            "create_time",
            "encrypted",
            "name",
            "size",
            "state",
            "type",
            "volume_id",
            "zone",
        ]:
            assert key in volume
        for key in ["attachments"]:
            assert type(volume[key]) is list
        for key in ["create_time"]:
            assert type(volume[key]) is datetime.datetime
        for key in ["encrypted"]:
            assert type(volume[key]) is bool
        for key in ["name", "volume_id", "zone"]:
            assert type(volume[key]) is str
        for key in ["size"]:
            assert type(volume[key]) is int
    volumes = [v for v in volumes if v["name"] != "-"]
    random_volume = volumes[3]
    volumes = list_volumes(
        volume_id="volume-" + str(random.randint(10000000, 99999999))
    )
    assert len(volumes) == 0
    volumes = list_volumes(volume_id=random_volume["volume_id"])
    assert len(volumes) == 1
    assert volumes[0]["volume_id"] == random_volume["volume_id"]


def test_create_and_terminate_instance():
    print("test_create_and_terminate_instance")
    # create a random name
    name = f"test-{str(random.randint(10000000,99999999))}-instance"

    # verify that test instance (tagged with token) does not exist    assert len(list_instances(name=))
    assert len(list_instances(name=name)) == 0, f"server name = {name} already exists"

    # deploy an instance
    device = "/dev/sda1"  # remember for later check
    disk_size = 29
    create_instance(
        name=name,
        instance_type="t2.micro",
        image_id="ami-097a2df4ac947655f",
        security_group_id="sg-0364d234122df6a66",
        key_name="visionair3d-ec2",
        device=device,
        disk_size=disk_size,
    )

    # # make sure the instance was created
    instance = list_instance(name=name)

    # check some things about the instance
    assert instance["name"] == name
    assert instance["state"] == "running"
    assert instance["instance_type"] == "t2.micro"
    assert instance["image_id"] == "ami-097a2df4ac947655f"
    assert instance["security_group_id"] == "sg-0364d234122df6a66"
    assert instance["termination_protection"] == True
    assert instance["instance_status"] == "initializing"
    assert instance["system_status"] == "initializing"
    instance_id = instance["instance_id"]

    # check storage
    volumes = instance["volumes"]
    assert len(volumes) == 1
    assert volumes[0]["delete_on_termination"] == True
    assert volumes[0]["status"] == "attached"
    volume_id = volumes[0]["volume_id"]
    assert volume_id.startswith("vol-")
    assert volumes[0]["name"] == device

    # verify the volume info
    volume = list_volume(volume_id=volume_id)
    assert volume["volume_id"] == volume_id
    assert volume["size"] == disk_size
    assert volume["type"] == "gp2"
    assert len(volume["attachments"]) == 1
    assert volume["attachments"][0]["instance_id"] == instance_id
    assert volume["attachments"][0]["device"] == device

    # try to terminate with termination_protection == True
    exception_raised = ""
    try:
        terminate_instance(instance_id=instance["instance_id"])
    except Exception as e:
        exception_raised = str(e)
    assert (
        "Modify its 'disableApiTermination' instance attribute and try again."
        in exception_raised
    )

    # clear the termination_protection and try again
    set_termination_protection(instance_id=instance["instance_id"], value=False)
    instance = list_instances(instance_id=instance["instance_id"])[0]
    assert instance["termination_protection"] == False
    terminate_instance(instance_id=instance["instance_id"])

    # verify that the instance was terminated
    instance = list_instances(instance_id=instance["instance_id"])[0]
    assert instance["state"] == "terminated"

    # verify that the volume is gone
    assert len(list_volumes(volume_id=volume_id)) == 0


def test_list_buckets():
    print("test_list_buckets")
    buckets = list_buckets()
    assert type(buckets) is list
    for b in buckets:
        assert "name" in b
        assert type(b["name"]) is str
        assert "creation_date" in b
        assert type(b["creation_date"]) is datetime.datetime
        assert "encryption" in b
        assert type(b["encryption"]) is str
        assert "versioning" in b
        assert type(b["versioning"]) is str
        assert "public_access_blocked" in b
        assert type(b["public_access_blocked"]) is str
        assert type(b["cors_allowed_origins"]) is list
        for origin in b["cors_allowed_origins"]:
            assert type(origin) is str


def test_delete_buckets():
    buckets = list_buckets()
    names = [b["name"] for b in buckets if "va3d-test-x-" in b["name"]]
    for name in names:
        print(name)
        delete_bucket(name)
    buckets = list_buckets()
    names = [b["name"] for b in buckets if "va3d-test-x-" in b["name"]]
    print([names])


def test_create_and_delete_buckets():
    print("test_create_and_delete_buckets")
    # create a random name
    name = f"va3d-test-x-{str(random.randint(10000000,99999999))}-bucket"

    # verify that test instance (tagged with token) does not exist    assert len(list_instances(name=))
    assert len(list_buckets(name=name)) == 0, f"server name = {name} already exists"

    print("creating bucket...")
    bucket = create_bucket(name=name, cors_allowed_origins=["http://localhost:8081"])
    assert bucket["name"] == name

    print("examining the bucket")
    bucket = list_bucket(name=name)
    pprint(bucket)
    assert bucket["name"] == name

    print("deleting the bucket")
    delete_bucket(name)
    buckets = list_buckets(name=name)
    names = [b["name"] for b in buckets if "va3d-test-x-" in b["name"]]
    print([names])


if __name__ == "__main__":
    test_initialization()
    test_list_instances()
    test_list_volumes()
    test_create_and_terminate_instance()
    test_list_buckets()
    test_create_and_delete_buckets()
    test_delete_buckets()
    print("done.")
