import os
import time
import subprocess
import tempfile
import requests
import ipaddress
import socket
import random
from typing import Optional, Callable, Dict
from enum import Enum

##################################
# SimpleVPNManager.py
#  Please read the instructions in the README.md file
#
# Author: VladoPortos
# Date: 2025-02-23
#
##################################


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

class SimpleVPNManager:
    def __init__(self, vpn_folder='vpn', logger=None, callback: Optional[Callable[[str, str], None]]=None):
        """
        Initialize VPN Manager

        Args:
            vpn_folder (str): Folder containing VPN config files
            logger: Optional custom logger instance
            callback: Optional callback function for status updates
                     Function signature: callback(level: str, message: str)
        """
        self.process = None
        self.vpn_folder = vpn_folder
        self.original_ip = None
        self.dns_backup = None
        self.dns_backup_file = '/etc/resolv.conf.backup'

        # Setup logging
        self.logger = logger
        self.callback = callback

    def _log(self, level: LogLevel, message: str):
        """Internal logging method that supports both logger and callback"""
        if self.logger:
            # Use provided logger
            if level == LogLevel.DEBUG:
                self.logger.debug(message)
            elif level == LogLevel.INFO:
                self.logger.info(message)
            elif level == LogLevel.WARNING:
                self.logger.warning(message)
            elif level == LogLevel.ERROR:
                self.logger.error(message)

        if self.callback:
            # Call user's callback function
            self.callback(level.value, message)

        if not self.logger and not self.callback:
            # Default behavior: print to stdout
            print(f"{level.value} - {message}")

    def get_current_ip(self):
        """Get current public IP address"""
        ip_services = [
            'https://ifconfig.me/ip',
            'https://api.ipify.org?format=json',
            'https://checkip.amazonaws.com'
        ]

        for url in ip_services:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    if url.endswith('/json'):
                        return response.json()['ip']
                    return response.text.strip()
            except Exception as e:
                self._log(LogLevel.DEBUG, f"Failed to get IP from {url}: {e}")
                continue

        raise RuntimeError("Failed to get current IP")

    def reset_network(self):
        """Reset network and DNS configuration"""
        try:
            # Kill any existing OpenVPN processes more gracefully
            try:
                # Check if OpenVPN is running first
                check_process = subprocess.run(['pgrep', 'openvpn'],
                                            check=False,
                                            capture_output=True,
                                            text=True)
                if check_process.returncode == 0:
                    subprocess.run(['killall', 'openvpn'], check=False, stderr=subprocess.DEVNULL)
                    time.sleep(2)  # Wait for processes to die
                    self._log(LogLevel.INFO, "OpenVPN processes terminated")
            except Exception as e:
                self._log(LogLevel.WARNING, f"Failed to kill OpenVPN processes: {e}")

            # Check if tun0 exists before trying to remove it
            try:
                check_tun = subprocess.run(['ip', 'link', 'show', 'tun0'],
                                         check=False,
                                         stderr=subprocess.DEVNULL,
                                         stdout=subprocess.DEVNULL)
                if check_tun.returncode == 0:
                    subprocess.run(['ip', 'link', 'delete', 'tun0'],
                                 check=False,
                                 stderr=subprocess.DEVNULL)
                    self._log(LogLevel.INFO, "Removed tun0 interface")
            except Exception as e:
                self._log(LogLevel.WARNING, f"Failed to remove tun0 interface: {e}")

            # In Docker, we might want to use a different DNS configuration approach
            if os.path.exists('/etc/resolv.conf'):
                try:
                    dns_config = [
                        "nameserver 127.0.0.11",  # Docker DNS
                        "nameserver 8.8.8.8",     # Google DNS fallback
                        "nameserver 1.1.1.1"      # Cloudflare DNS fallback
                    ]
                    with open('/etc/resolv.conf', 'w') as f:
                        f.write('\n'.join(dns_config))
                    self._log(LogLevel.INFO, "Reset DNS configuration")
                except Exception as e:
                    self._log(LogLevel.ERROR, f"Failed to update DNS config: {e}")
                    return False

            return True

        except Exception as e:
            self._log(LogLevel.ERROR, f"Failed to reset network: {e}")
            return False

    def _get_docker_networks(self):
        """Get Docker networks and their CIDR ranges"""
        try:
            # First get all network interfaces
            result = subprocess.run(['ip', 'addr'], capture_output=True, text=True, check=True)
            interfaces = result.stdout.splitlines()

            # Find eth0 or similar interface and its network
            current_if = None
            for line in interfaces:
                if ': eth' in line or ': en' in line:  # Look for ethernet interfaces
                    current_if = line.split(':')[1].strip()
                elif current_if and 'inet ' in line:  # Get IPv4 address for the interface
                    # Extract CIDR notation (e.g., 172.17.0.2/16)
                    parts = line.strip().split()
                    for part in parts:
                        if '/' in part and part.split('/')[0].count('.') == 3:
                            try:
                                # Convert container IP to network CIDR
                                # e.g., 172.17.0.2/16 -> 172.17.0.0/16
                                container_net = ipaddress.ip_interface(part).network
                                self._log(LogLevel.INFO, f"Detected Docker network: {container_net}")
                                return [str(container_net)]
                            except Exception as e:
                                self._log(LogLevel.ERROR, f"Failed to parse interface IP {part}: {e}")

            # If we couldn't find our network, try ip route as fallback
            result = subprocess.run(['ip', 'route'], capture_output=True, text=True, check=True)
            routes = result.stdout.splitlines()

            docker_networks = []
            for route in routes:
                # Look for docker networks (usually docker0 or br-*)
                if 'docker0' in route or 'br-' in route:
                    parts = route.split()
                    if len(parts) >= 1:
                        network = parts[0]  # The CIDR is usually the first part
                        if '/' in network:  # Ensure it's a CIDR notation
                            docker_networks.append(network)

            if docker_networks:
                self._log(LogLevel.INFO, f"Found Docker networks from routes: {docker_networks}")
                return docker_networks

            # If no networks found, use default Docker network range
            self._log(LogLevel.WARNING, "No Docker networks found, using default route")
            return ["172.16.0.0/12"]  # Default Docker network range

        except Exception as e:
            self._log(LogLevel.ERROR, f"Failed to detect Docker networks: {e}")
            return ["172.16.0.0/12"]  # Fallback to default

    def _get_random_vpn_file(self):
        """Get a random VPN file from the configured folder"""
        try:
            ovpn_files = [f for f in os.listdir(self.vpn_folder) if f.endswith('.ovpn')]
            if not ovpn_files:
                self._log(LogLevel.ERROR, f"No OVPN files found in {self.vpn_folder} directory")
                return None

            # Select a random VPN file
            chosen_file = random.choice(ovpn_files)
            self._log(LogLevel.INFO, f"Selected VPN config: {chosen_file}")
            return os.path.join(self.vpn_folder, chosen_file)
        except Exception as e:
            self._log(LogLevel.ERROR, f"Failed to get VPN file: {e}")
            return None

    def _prepare_vpn_files(self, ovpn_file):
        """Prepare VPN config and auth files"""
        try:
            # Get Docker networks
            docker_networks = self._get_docker_networks()
            docker_routes = []
            for network in docker_networks:
                # Convert CIDR to route command
                try:
                    net = ipaddress.ip_network(network)
                    docker_routes.append(f"route {net.network_address} {net.netmask} net_gateway")
                except Exception as e:
                    self._log(LogLevel.ERROR, f"Failed to parse network {network}: {e}")
                    continue

            # Read original config
            with open(ovpn_file, 'r') as f:
                config_lines = f.read().splitlines()

            # Remove any existing routing commands and auth-user-pass directives
            config_lines = [
                line for line in config_lines
                if not any(x in line for x in [
                    'redirect-gateway',
                    'route ',
                    'route-ipv6',
                    'auth-user-pass'  # Remove existing auth-user-pass lines
                ])
            ]

            # Add our custom routing and auth configuration
            custom_config = [
                "# Added by dns-ripper worker",
                "redirect-gateway def1 bypass-dhcp",  # Don't let DHCP override our routes
            ] + docker_routes  # Add Docker network routes

            # Create auth file if credentials are present in environment
            auth_file = tempfile.mktemp()
            vpn_user = os.getenv('VPN_USER', '')
            vpn_pass = os.getenv('VPN_PASSWORD', '')

            if not vpn_user or not vpn_pass:
                self._log(LogLevel.ERROR, "VPN credentials not found in environment variables")
                return None, None

            with open(auth_file, 'w') as f:
                f.write(f"{vpn_user}\n{vpn_pass}")

            # Add auth file directive to config
            custom_config.append(f"auth-user-pass {auth_file}")

            # Write config to temporary file
            config_file = tempfile.mktemp(suffix='.ovpn')
            with open(config_file, 'w') as f:
                f.write('\n'.join(config_lines + custom_config))

            return config_file, auth_file

        except Exception as e:
            self._log(LogLevel.ERROR, f"Failed to prepare VPN files: {e}")
            return None, None

    def start_vpn(self):
        """Start VPN connection with a random config"""
        # Get a random VPN config
        ovpn_file = self._get_random_vpn_file()
        if not ovpn_file:
            return None

        config_file, auth_file = self._prepare_vpn_files(ovpn_file)
        if not config_file or not auth_file:
            self._log(LogLevel.ERROR, "Failed to prepare VPN configuration files")
            return None

        try:
            # Reset network first
            if not self.reset_network():
                raise Exception("Failed to reset network")

            # Get IP before VPN
            before_ip = self.get_current_ip()
            self._log(LogLevel.INFO, f"Current IP: {before_ip}")

            # Start OpenVPN with verbose logging
            self.process = subprocess.Popen(
                ['openvpn', '--config', config_file, '--verb', '4'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Wait for connection to establish
            time.sleep(10)

            # Check if process died
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                stdout_text = stdout.decode()
                stderr_text = stderr.decode()

                # Log the output for debugging
                if stdout_text:
                    for line in stdout_text.splitlines():
                        if line.strip():
                            self._log(LogLevel.ERROR, f"OpenVPN: {line}")
                if stderr_text:
                    for line in stderr_text.splitlines():
                        if line.strip():
                            self._log(LogLevel.ERROR, f"OpenVPN Error: {line}")

                # Check for auth failure
                if "auth failed" in stderr_text.lower():
                    raise Exception(f"OpenVPN authentication failed: {stderr_text}")

                raise Exception("OpenVPN process terminated unexpectedly")

            # If we get here, the process is still running
            self._log(LogLevel.INFO, "OpenVPN process started and running")

            # Verify IP changed
            after_ip = self.get_current_ip()
            self._log(LogLevel.INFO, f"VPN connected. New IP: {after_ip}")

            if after_ip == before_ip:
                raise Exception("IP address did not change after VPN connection")

            return after_ip

        except Exception as e:
            self._log(LogLevel.ERROR, f"VPN setup failed: {e}")
            self.reset_network()  # Try to clean up
            return None

        finally:
            # Cleanup temporary files
            if auth_file:
                os.unlink(auth_file)
            if config_file:
                os.unlink(config_file)

    def is_vpn_active(self):
        """Check if VPN process is still running"""
        if self.process is None:
            return False

        # Check if process is still running
        if self.process.poll() is None:
            # Also verify tun0 interface exists as additional check
            try:
                result = subprocess.run(['ip', 'link', 'show', 'tun0'],
                                     check=False,
                                     capture_output=True,
                                     text=True)
                return result.returncode == 0
            except Exception:
                return False
        return False

    def stop_vpn(self):
        """Clean up VPN resources regardless of state"""
        try:
            terminated = False
            # Kill OpenVPN process if it exists
            if self.process:
                try:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=5)
                        terminated = True
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait()
                        terminated = True
                except Exception as e:
                    self._log(LogLevel.WARNING, f"Error terminating OpenVPN process: {e}")
                finally:
                    self.process = None

            # Reset network configuration
            self.reset_network()

            if terminated:
                self._log(LogLevel.INFO, "OpenVPN processes terminated")

            return True
        except Exception as e:
            self._log(LogLevel.ERROR, f"Error during VPN cleanup: {e}")
            return False
