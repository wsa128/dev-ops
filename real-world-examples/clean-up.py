import infra
from pprint import pprint


def clean_up(instance_id):
    instance = infra.list_instance(instance_id=instance_id)
    assert instance["name"].startswith("test-")
    print(f"Terminating instance {instance['name']}/{instance_id}")
    if instance["state"] == "terminated":
        print(f"Instance {instance_id} is already terminated.")
    if instance["termination_protection"]:
        infra.set_termination_protection(instance_id=instance_id, value=False)
    print(instance["volumes"])
    assert len(instance["volumes"]) == 1
    volume_id = instance["volumes"][0]["volume_id"]
    volume = infra.list_volume(volume_id=volume_id)
    infra.terminate_instance(instance_id=instance_id)
    instance = infra.list_instance(instance_id=instance_id)
    assert (
        instance["state"] == "terminated"
    ), f"Instance {instance_id} was not terminated."
    print(f"Instance {instance_id} was terminated")
    volumes = infra.list_volumes(volume_id=volume_id)
    assert len(volumes) == 0, f"Volume {volume_id} was not deleted."
    print(f"Volume {volume_id} was deleted.")


if __name__ == "__main__":
    instances = [i for i in infra.list_instances() if i["state"] != "terminated"]
    for i in instances:
        if (i["name"]).startswith("test-"):
            clean_up(i["instance_id"])
