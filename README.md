# Simple VPN Manager

A flexible and easy-to-use VPN manager for Python applications that supports custom logging and automatic VPN configuration selection.

I sometimes need to use VPN in container, without host going into VPN completely. This is a simple solution for that. VPN is starts only inside the container and host is not affected.

---

## ☕ Buy Me a Coffee (or a Beer!)

If you like this project and want to support my caffeine-fueled coding sessions, you can buy me a coffee (or a beer, I won't judge! 🍻) on Ko-fi:

[![Support me on Ko-fi](img/support_me_on_kofi_badge_red.png)](https://ko-fi.com/vladoportos)

Every donation helps to proofe to my wife that I'm not a complete idiot :D

---

## Features

- Automatic random VPN configuration selection
- Flexible logging system with multiple output options
- Docker network detection and routing
- IP change verification
- Clean connection and disconnection handling

## Installation

1. Ensure you have OpenVPN installed in your environment
2. Place your `.ovpn` configuration files in a `vpn` directory
3. Set up your environment variables:
   ```env
   VPN_USER=your_vpn_username
   VPN_PASSWORD=your_vpn_password
   ```

## Usage

### Basic Usage

```python
from SimpleVPNManager import SimpleVPNManager

# Create VPN manager with default stdout logging
vpn = SimpleVPNManager(vpn_folder='vpn')

# Start VPN (automatically selects random config)
new_ip = vpn.start_vpn()
if new_ip:
    print(f"Connected! New IP: {new_ip}")

    # Keep connection active
    while vpn.is_vpn_active():
        time.sleep(1)
```

### Using Python Logger

```python
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create VPN manager with Python logger
vpn = SimpleVPNManager(
    vpn_folder='vpn',
    logger=logger
)
```

### Using Custom Callback

```python
def status_callback(level: str, message: str):
    # Handle status updates (e.g., update GUI, send to webhook)
    print(f"VPN Status [{level}]: {message}")

# Create VPN manager with callback
vpn = SimpleVPNManager(
    vpn_folder='vpn',
    callback=status_callback
)
```

### Docker Support

When running in Docker, ensure your container has the necessary capabilities:

```yaml
services:
  vpn-service:
    build: .
    cap_add:
      - NET_ADMIN
    devices:
      - /dev/net/tun:/dev/net/tun
```

## API Reference

### SimpleVPNManager

#### Constructor

```python
SimpleVPNManager(
    vpn_folder='vpn',
    logger=None,
    callback=None
)
```

- `vpn_folder`: Directory containing `.ovpn` configuration files
- `logger`: Optional Python logger instance
- `callback`: Optional callback function for status updates

#### Methods

- `start_vpn()`: Start VPN connection with random config. Returns new IP on success, None on failure
- `stop_vpn()`: Stop VPN connection and cleanup resources
- `is_vpn_active()`: Check if VPN connection is active
- `get_current_ip()`: Get current public IP address

## Logging System

The VPN manager supports three logging modes:

1. **Python Logger**: Use standard Python logging module
2. **Callback Function**: Custom handling of status messages
3. **Default stdout**: Simple print output if no logger or callback provided

### Log Levels

- DEBUG: Detailed information for debugging
- INFO: General operational information
- WARNING: Warning messages for potential issues
- ERROR: Error messages for operation failures

## Error Handling

The VPN manager includes comprehensive error handling for:

- Network interface issues
- Authentication failures
- Connection timeouts
- IP verification failures
- Configuration file errors

## Requirements

- Python 3.6+
- OpenVPN
- Docker (if running in container)
- Required Python packages (see requirements.txt)

## License

Do whatever you want with this project. I'm not responsible for anything. I was never here. :D
