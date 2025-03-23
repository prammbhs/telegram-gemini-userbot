"""
Telegram Connection Checker
A utility for checking connectivity to Telegram servers
"""

import socket
import logging
import asyncio
import time
import requests
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('TelegramConnectionChecker')

class TelegramConnectionChecker:
    """Utility class for checking Telegram server connectivity"""
    
    # Known Telegram servers across various DCs
    TELEGRAM_SERVERS = [
        ("api.telegram.org", 443),
        ("149.154.167.50", 443),  # Telegram DC1
        ("149.154.167.51", 443),  # Telegram DC2
        ("149.154.175.100", 443), # Telegram DC3
        ("149.154.175.50", 443),  # Telegram DC4
        ("149.154.167.91", 443),  # Telegram DC5
    ]
    
    @staticmethod
    def check_socket_connection(server, port, timeout=3):
        """Check if we can establish a TCP connection to the server:port"""
        try:
            sock = socket.create_connection((server, port), timeout=timeout)
            sock.close()
            return True
        except (socket.timeout, socket.gaierror, ConnectionError, OSError) as e:
            logger.debug(f"Connection to {server}:{port} failed: {str(e)}")
            return False
    
    @staticmethod
    def check_http_connection(timeout=3):
        """Check if we can reach Telegram's API via HTTPS"""
        try:
            response = requests.get("https://api.telegram.org/", timeout=timeout)
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    @classmethod
    def check_telegram_connection(cls, check_multiple=True):
        """
        Check if Telegram servers are reachable
        
        Args:
            check_multiple: If True, try multiple servers. If False, only check api.telegram.org
            
        Returns:
            tuple: (is_reachable, working_server, error_message)
        """
        if check_multiple:
            servers_to_check = cls.TELEGRAM_SERVERS
        else:
            servers_to_check = [("api.telegram.org", 443)]
            
        # Try HTTP connection first
        try:
            if cls.check_http_connection():
                return True, "api.telegram.org:443", "HTTPS connection successful"
        except:
            pass  # Fall back to socket checks
        
        # Check sockets in parallel for speed
        with ThreadPoolExecutor(max_workers=len(servers_to_check)) as executor:
            future_to_server = {
                executor.submit(cls.check_socket_connection, server, port): (server, port)
                for server, port in servers_to_check
            }
            
            for future in future_to_server:
                server, port = future_to_server[future]
                try:
                    is_reachable = future.result()
                    if is_reachable:
                        return True, f"{server}:{port}", f"Socket connection to {server}:{port} successful"
                except Exception:
                    continue
        
        # If we get here, all connections failed
        return False, None, "Could not connect to any Telegram servers"

    @classmethod
    async def check_telegram_connection_async(cls, check_multiple=True):
        """
        Asynchronous version of check_telegram_connection
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, cls.check_telegram_connection, check_multiple
        )

    @classmethod
    def diagnose_connection_problems(cls):
        """
        Run a comprehensive diagnosis of network connectivity issues
        that might affect Telegram connections
        
        Returns:
            dict: Results of the diagnosis with suggestions
        """
        results = {
            "internet_connected": False,
            "telegram_api_reachable": False,
            "telegram_dc_reachable": False,
            "socket_errors": [],
            "suggestions": []
        }
        
        # Check basic internet connectivity
        try:
            # Try to connect to a reliable service
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            results["internet_connected"] = True
        except Exception as e:
            results["socket_errors"].append(f"Basic internet check failed: {str(e)}")
            results["suggestions"].append("Check your internet connection")
        
        # Check if Telegram API is reachable via HTTPS
        if results["internet_connected"]:
            try:
                response = requests.get("https://api.telegram.org/", timeout=5)
                results["telegram_api_reachable"] = response.status_code == 200
                if not results["telegram_api_reachable"]:
                    results["suggestions"].append(f"Telegram API returned status code {response.status_code}")
            except requests.RequestException as e:
                results["suggestions"].append(f"Cannot reach Telegram API via HTTPS: {str(e)}")
        
        # Check if at least one Telegram DC is reachable
        dc_results = []
        for server, port in cls.TELEGRAM_SERVERS[1:]:  # Skip api.telegram.org and check DCs directly
            try:
                success = cls.check_socket_connection(server, port, timeout=5)
                dc_results.append((server, success))
                if success:
                    results["telegram_dc_reachable"] = True
            except Exception as e:
                dc_results.append((server, False))
                results["socket_errors"].append(f"Error checking {server}: {str(e)}")
        
        # Compile suggestions based on findings
        if not results["telegram_dc_reachable"]:
            results["suggestions"].append("Cannot connect to any Telegram data centers. This could indicate:")
            results["suggestions"].append("- Your ISP might be blocking Telegram")
            results["suggestions"].append("- A firewall might be blocking outgoing connections")
            results["suggestions"].append("- Try using a different network or VPN")
        
        # Check for WinError 10054 specifically (connection reset by peer)
        windows_specific = False
        for error in results["socket_errors"]:
            if "10054" in error:
                windows_specific = True
                results["suggestions"].append("Your connection to Telegram is being reset (WinError 10054):")
                results["suggestions"].append("- This often indicates a firewall or antivirus issue")
                results["suggestions"].append("- Try temporarily disabling your firewall/antivirus")
                break
        
        return results

# Test the connection checker when run directly
if __name__ == "__main__":
    is_reachable, server, message = TelegramConnectionChecker.check_telegram_connection()
    if is_reachable:
        print(f"✅ Telegram is reachable via {server}: {message}")
    else:
        print(f"❌ Telegram is not reachable: {message}")
