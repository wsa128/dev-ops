import argparse
import subprocess
import time
from pprint import pprint


def run(host, key, command):
    remote_command = f"ssh ubuntu@{host} -i {key}  -o LogLevel=ERROR -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no {command}"
    result = subprocess.run(remote_command.split(), capture_output=True)
    stderr = result.stderr.decode(encoding="UTF-8").strip()
    if stderr != "":
        raise Exception(f"{stderr} ( running: $ {command} )")
    return result.stdout.decode(encoding="UTF-8").strip()


def test_run(host, key):
    print("testing run() ...")
    try:
        output = run(host, key, "nosuchcommand")
        assert False, "This command should have failed."
    except Exception as e:
        assert (
            str(e)
            == "bash: nosuchcommand: command not found ( running: $ nosuchcommand )"
        )
    output = run(
        host,
        key,
        "hostname",
    )
    print(host)
    print(output)
    assert output == host.replace(".", "-")
    output = run(
        host,
        key,
        "ls -la /",
    )
    assert output.startswith("total")


def ps(host, key):
    processes = run(host, key, "ps -aeo pid,command")
    processes = processes.strip().split("\n")
    processes = [
        [line[0:8].strip(), line[8:]]
        for line in processes
        if line != "" and "PID COMMAND" not in line
    ]
    return processes


def test_ps(host, key):
    print("testing ps() ...")
    processes = ps(host, key)
    assert type(processes) is list
    assert type(processes[0]) is list
    assert len([p for p in processes if "/systemd/" in p[1]]) > 0
    assert len([p for p in processes if p[1] == "ps -aeo pid,command"]) > 0
    assert len([int(p[0]) for p in processes]) == len(
        processes
    )  # forces int eval for all p[0]


def kill(host, key, pid=None, pattern=None):
    if pattern:
        assert pid == None, "can't specify both name and id for _kill_ function."
        processes = ps(host, key)
        processes = [p for p in processes if pattern in p[1]]
        if len(processes) == 0:
            return "pattern does not match any process"
        assert len(processes) == 1, "pattern matches more than one process."
        pid, command = processes[0]
    if pid:
        pid = int(pid)
        output = run(host, key, f"kill -9 {pid}")
        return output


def test_kill_by_pid(host, key):
    # kill by PID
    processes = ps(host, key)
    processes = [p for p in processes if "ticker" in p[1]]
    print(processes)
    assert len(processes) == 1, "_ticker_ process is not running."
    pid, command = processes[0]
    kill(host, key, pid=pid)
    time.sleep(2)
    processes = ps(host, key)
    processes = [p for p in processes if "ticker" in p[1]]
    print(processes)
    assert len(processes) == 0, "_ticker process is still running."


def test_kill_by_pattern(host, key):
    # kill by pattern
    processes = ps(host, key)
    processes = [p for p in processes if "ticker" in p[1]]
    print(processes)
    assert len(processes) == 1, "_ticker_ process is not running."
    pid, command = processes[0]
    kill(host, key, pattern="ticker")
    time.sleep(2)
    processes = ps(host, key)
    processes = [p for p in processes if "ticker" in p[1]]
    print(processes)
    assert len(processes) == 0, "_ticker process is still running."


def screens(host, key, assert_screen=None):
    run(host, key, "screen -wipe")
    output = run(host, key, "screen -ls").split("\n")
    assert len(output) > 0
    if "No Sockets" in output[0]:
        if assert_screen is not None:
            assert False, f"Screen '{assert_screen}' not found"
        return []

    lines = [l for l in output if l != ""]
    lines = [l for l in lines if "There is a screen" not in l]
    lines = [l for l in lines if "There are screens" not in l]
    lines = [l for l in lines if "Socket in" not in l]
    lines = [l for l in lines if "Sockets in" not in l]

    session_ids = [l.strip().split("\t")[0] for l in lines]
    processes = [p for p in ps(host, key) if "SCREEN" in p[1]]

    screen_list = []
    for session_id in session_ids:
        pid = session_id.split(".")[0]
        name = session_id.replace(pid + ".", "")
        session_info = f"SCREEN -dmS {name} bash -c"
        screen = {"id": session_id, "pid": pid, "name": name, "command": "???"}

        for p in processes:
            if pid == p[0] and p[1].startswith(session_info):
                screen["command"] = p[1].replace(session_info, "").strip()

        screen_list.append(screen)

    print(screen_list)

    if assert_screen is not None:
        matching_screen = [
            screen for screen in screen_list if screen["name"] == assert_screen
        ]
        assert len(matching_screen) == 1, f"Screen '{assert_screen}' not found"

    return screen_list


def start(host, key, name, command, logfile=None):
    if logfile:
        log_options = f"-L -Logfile {logfile}"
    else:
        log_options = ""
    output = run(host, key, f'screen -dmS {name} {log_options} bash -c "{command}"')
    return output


def stop(host, key, name, exact=False):
    start = time.time()
    if exact:
        screen_list = [
            screen for screen in screens(host, key) if name == screen["name"]
        ]
    else:
        screen_list = [
            screen for screen in screens(host, key) if name in screen["name"]
        ]
    while len(screen_list) > 0:
        if (time.time() - start) > 10.0:
            raise Exception(f"Time expired while trying to stop all '{name}' screens.")
        for screen in screen_list:
            kill(host, key, pid=screen["pid"])
            run(host, key, "screen -wipe")
        screen_list = [screen for screen in screens(host, key) if name in screen["id"]]
    return


from random import randint


def test_screens_start_kill_stop(host, key):
    print("testing screens start kill stop()")

    def cleanup():
        # kill any old testing- screens
        screen_list = [
            screen for screen in screens(host, key) if "testing-" in screen["name"]
        ]
        if len(screen_list) > 0:
            print("Note: Stopping old testing- screens...")
        stop(host, key, "testing-")
        screen_list = [
            screen for screen in screens(host, key) if "testing-" in screen["name"]
        ]
        assert len(screen_list) == 0, "Error: Old testing- screens are still running."

        # delete old log files
        run(host, key, "rm -rf ~/testing-*.log")
        output = run(host, key, "ls ~").split("\n")
        files = [file for file in output if "testing-" in file]
        assert len(files) == 0, "Error: Old testing- logs are still remaining."

    cleanup()

    # start a testing screen
    screen_name = f"testing-{randint(1000000,9999999)}"
    start(
        host,
        key,
        screen_name,
        "while true; do date; sleep 2; done",
        logfile=f"{screen_name}.screen.log",
    )

    # verify the screen was started
    screen_list = [
        screen for screen in screens(host, key) if screen_name == screen["name"]
    ]
    assert len(screen_list) == 1

    # verify the log was created
    output = run(host, key, "ls ~").split("\n")
    files = [file for file in output if f"{screen_name}.screen.log" in file]
    assert len(files) == 1

    # wait a few seconds and check the log file
    time.sleep(6)
    output = run(host, key, f"cat ~/{screen_name}.screen.log").split("\n")
    assert len(output) >= 1
    for line in output:
        assert " UTC " in line
        assert (
            len(line.strip().split(":")) == 3
        ), f"Line {line} should have three parts."

    # stop the testing screen
    stop(host, key, screen_name)

    # verify that the screen was stopped
    screen_list = [
        screen for screen in screens(host, key) if screen_name == screen["name"]
    ]
    assert len(screen_list) == 0

    cleanup()
    print("remote screen testing complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--host", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--name")
    parser.add_argument("--command")
    parser.add_argument("--pid")
    parser.add_argument("--pattern")
    parser.add_argument(
        "operation",
        type=str,
        choices=["run", "ps", "screens", "start", "stop", "kill", "test"],
    )
    args = parser.parse_args().__dict__
    host = args["host"]
    key = args["key"]
    name = args["name"]
    command = args["command"]
    pid = args["pid"]
    pattern = args["pattern"]
    operation = args["operation"]

    if operation == "run":
        assert command, "A command is required for the 'run' operation."
        print(run(host, key, command))

    if operation == "ps":
        for line in ps(host, key):
            print(f"{line[0]} {line[1]}")

    if operation == "screens":
        screens(host, key, assert_screen=name)

    if operation == "start":
        assert name, "A name is required for the 'start' operation."
        assert command, "A command is required for the 'start' operation."
        start(host, key, name, command, logfile=f"{name}.screen.log")

    if operation == "stop":
        assert name, "A name is required for the 'stop' operation."
        stop(host, key, name)

    if operation == "kill":
        assert (
            pid or pattern
        ), "A --pid (process ID as integer) or --pattern (command substring) is required for the 'kill' operation."
        print([pid, pattern])
        assert not (
            pid and pattern
        ), "Only one of --pid (process ID as integer) or --pattern (command substring) is allowed for the 'kill' operation."
        if pid:
            assert (
                pid.isdigit()
            ), "A PID (--pid <PID>) must consist only of digits for the 'kill' operation."
            kill(host, key, pid=int(pid))
        if pattern:
            kill(host, key, pattern=pattern)

    if operation == "test":
        # test_run(host, key)
        # test_ps(host, key)
        test_kill_by_pattern(host, key)
        test_screens_start_kill_stop(host, key)
