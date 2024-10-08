"""We need to write a custom plugin to compare the logs generated in `foo-transmit` with the logs generated by `foo-receive`. Specifically, we are concerned with writing the following comparison logic:

- Are the number of packets transmitted the same number as the packets that are received?

- Are the sizes of all packets transmitted equal to those received?

- What is the mean, median, and 99.9% latency between transmission and receipt?

Write a custom Ansible plugin to take as input the two log files, and generate the above statistics for integration with playbooks. """

from ansible.module_utils.basic import AnsibleModule
import os
import statistics
from typing import List, Tuple, Dict, Generator, Optional
from collections import namedtuple

LogEntry = namedtuple('LogEntry', ['timestamp', 'byte_count'])

def read_log(logfile: str) -> Generator[LogEntry, None, None]:
    """
    Reads a log file and yields LogEntry objects.

    Args:
        logfile (str): Path to the log file.

    Yields:
        LogEntry: A named tuple containing timestamp and byte_count.

    Raises:
        FileNotFoundError: If the log file does not exist.
        ValueError: If a log entry is not in the expected format.
    """
    if not os.path.exists(logfile):
        raise FileNotFoundError(f"Log file {logfile} does not exist")
    
    with open(logfile, 'r') as f:
        for line_num, line in enumerate(f, 1):
            try:
                timestamp_str, byte_count_str = line.strip().split(',')
                yield LogEntry(int(timestamp_str), int(byte_count_str))
            except ValueError as e:
                raise ValueError(f"Invalid log entry format at line {line_num}: {line.strip()}") from e

def compare_packets(transmit_entries: List[LogEntry], receive_entries: List[LogEntry]) -> Tuple[bool, Optional[str]]:
    """
    Compares the number and sizes of packets between transmit and receive logs.

    Args:
        transmit_entries (List[LogEntry]): List of transmit log entries.
        receive_entries (List[LogEntry]): List of receive log entries.

    Returns:
        Tuple[bool, Optional[str]]: A tuple containing a boolean indicating success and an optional error message.
    """
    if len(transmit_entries) != len(receive_entries):
        return False, f"Packet count mismatch: {len(transmit_entries)} transmitted vs {len(receive_entries)} received"

    for i, (t_entry, r_entry) in enumerate(zip(transmit_entries, receive_entries)):
        if t_entry.byte_count != r_entry.byte_count:
            return False, f"Packet size mismatch at index {i}: sent {t_entry.byte_count}, received {r_entry.byte_count}"

    return True, None

def calculate_latencies(transmit_entries: List[LogEntry], receive_entries: List[LogEntry]) -> List[int]:
    """
    Calculates latencies between transmit and receive timestamps.

    Args:
        transmit_entries (List[LogEntry]): List of transmit log entries.
        receive_entries (List[LogEntry]): List of receive log entries.

    Returns:
        List[int]: List of latencies in milliseconds.

    Raises:
        ValueError: If a receive timestamp is earlier than its corresponding transmit timestamp.
    """
    latencies = []
    for i, (t_entry, r_entry) in enumerate(zip(transmit_entries, receive_entries)):
        latency = r_entry.timestamp - t_entry.timestamp
        if latency < 0:
            raise ValueError(f"Invalid latency at index {i}: receive time earlier than transmit time")
        latencies.append(latency)
    return latencies

def calculate_statistics(latencies: List[int]) -> Dict[str, float]:
    """
    Calculates mean, median, and 99.9% latency statistics.

    Args:
        latencies (List[int]): List of latencies in milliseconds.

    Returns:
        Dict[str, float]: Dictionary containing mean, median, and 99.9% latency statistics.
    """
    return {
        "mean_latency": statistics.mean(latencies),
        "median_latency": statistics.median(latencies),
        "99.9_latency": statistics.quantiles(latencies, n=1000)[-1]
    }

def process_logs(transmit_log: str, receive_log: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Process transmit and receive logs to compare packets and calculate latency statistics.

    Args:
        transmit_log (str): Path to the transmit log file.
        receive_log (str): Path to the receive log file.

    Returns:
        Tuple[bool, Dict[str, Any]]: A tuple containing a boolean indicating success and a dictionary with results or an error message.
    """
    try:
        transmit_entries = list(read_log(transmit_log))
        receive_entries = list(read_log(receive_log))

        success, error_message = compare_packets(transmit_entries, receive_entries) # optional error message
        if not success:
            return False, {"error": error_message}

        latencies = calculate_latencies(transmit_entries, receive_entries)
        statistics = calculate_statistics(latencies)
        
        return True, {
            "packet_count": len(transmit_entries),
            **statistics,
            "latencies": latencies
        }
    except Exception as e:
        return False, {"error": str(e)}

def main():
    module = AnsibleModule(
        argument_spec=dict(
            transmit_log=dict(type='str', required=True),
            receive_log=dict(type='str', required=True)
        )
    )

    transmit_log = module.params['transmit_log']
    receive_log = module.params['receive_log']

    success, result = process_logs(transmit_log, receive_log)
    if success:
        module.exit_json(changed=False, result=result)
    else:
        module.fail_json(msg=result['error'])

if __name__ == '__main__':
    main()
