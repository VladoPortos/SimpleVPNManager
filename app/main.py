import logging
import time
from SimpleVPNManager import SimpleVPNManager

##################################
#
#  Sample code to start VPN and keep it active
#
# Author: VladoPortos
# Date: 2025-02-23
#
##################################


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    # Initialize VPN manager with logger
    vpn = SimpleVPNManager(
        vpn_folder='vpn',
        logger=logger
    )

    try:
        # Start VPN with random config
        new_ip = vpn.start_vpn()
        if new_ip:
            logger.info(f"Successfully connected to VPN. New IP: {new_ip}")

            # Keep the connection active
            while vpn.is_vpn_active():
                time.sleep(1)
        else:
            logger.error("Failed to establish VPN connection")

    except KeyboardInterrupt:
        logger.info("Received interrupt signal, stopping VPN...")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
    finally:
        vpn.stop_vpn()
        logger.info("VPN stopped")

if __name__ == "__main__":
    main()
