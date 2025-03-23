"""
Windows Network Helper
A utility for Windows users to diagnose and fix Telegram connection issues
"""

import os
import sys
import ctypes
import socket
import logging
import platform
import subprocess
import webbrowser
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('WindowsNetworkHelper')

class WindowsNetworkHelper:
    """Helper class for diagnosing and fixing network issues on Windows"""
    
    # Known Telegram servers
    TELEGRAM_SERVERS = [
        ("api.telegram.org", 443),
        ("149.154.167.50", 443),  # Telegram DC1
        ("149.154.167.51", 443),  # Telegram DC2
        ("149.154.175.100", 443), # Telegram DC3
        ("149.154.175.50", 443),  # Telegram DC4
        ("149.154.167.91", 443),  # Telegram DC5
    ]
    
    @staticmethod
    def is_windows():
        """Check if running on Windows"""
        return platform.system() == 'Windows'
    
    @staticmethod
    def is_admin():
        """Check if running with admin privileges"""
        if not WindowsNetworkHelper.is_windows():
            return False
            
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False
    
    @staticmethod
    def check_telegram_connection():
        """Check if we can connect to Telegram servers"""
        results = {'api': False, 'dcs': []}
        
        # Try to connect to api.telegram.org
        try:
            socket.create_connection(("api.telegram.org", 443), timeout=5)
            results['api'] = True
        except:
            pass
            
        # Try to connect to data centers
        for i, (server, port) in enumerate(WindowsNetworkHelper.TELEGRAM_SERVERS[1:], 1):
            try:
                socket.create_connection((server, port), timeout=5)
                results['dcs'].append(i)
            except:
                pass
                
        return results
    
    @staticmethod
    def check_firewall_for_python():
        """Check if Windows Firewall is likely blocking Python/Telegram"""
        if not WindowsNetworkHelper.is_windows():
            return False
            
        # First check if we can connect to Telegram
        conn_results = WindowsNetworkHelper.check_telegram_connection()
        
        # If we can connect to at least one server, firewall probably not blocking
        if conn_results['api'] or conn_results['dcs']:
            return {
                'blocked': False,
                'connected_to': 'API' if conn_results['api'] else f"DC{conn_results['dcs'][0]}"
            }
            
        # Check if firewall is enabled
        try:
            output = subprocess.check_output(
                ['netsh', 'advfirewall', 'show', 'currentprofile'], 
                universal_newlines=True
            )
            firewall_on = "State                      ON" in output
            
            if not firewall_on:
                return {
                    'blocked': False,
                    'reason': 'Firewall disabled but still cannot connect - may be ISP blocking'
                }
                
            # Check if python.exe is in the allowed list
            python_path = sys.executable
            allowed_output = subprocess.check_output(
                ['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=all'], 
                universal_newlines=True
            )
            
            python_allowed = python_path.lower() in allowed_output.lower()
            
            return {
                'blocked': not python_allowed,
                'reason': 'Python not in Windows Firewall exceptions' if not python_allowed else 'Unknown'
            }
        except:
            return {
                'blocked': True,
                'reason': 'Could not determine firewall status'
            }
    
    @staticmethod
    def add_python_to_firewall():
        """Attempt to add Python to Windows Firewall exceptions"""
        if not WindowsNetworkHelper.is_windows():
            return False
            
        if not WindowsNetworkHelper.is_admin():
            logger.error("Admin privileges required to modify firewall")
            return False
            
        try:
            python_path = sys.executable
            cmd = [
                'netsh', 'advfirewall', 'firewall', 'add', 'rule',
                f'name=Python Telegram Bot',
                f'program={python_path}',
                'dir=out', 'action=allow', 'enable=yes', 'profile=any'
            ]
            
            subprocess.run(cmd, check=True)
            return True
        except Exception as e:
            logger.error(f"Failed to add firewall rule: {e}")
            return False
    
    @classmethod
    def run_network_diagnostics(cls):
        """Run full network diagnostics for Telegram connection issues"""
        results = {
            'timestamp': datetime.now().isoformat(),
            'os': platform.system(),
            'is_windows': cls.is_windows(),
            'internet_connected': False,
            'can_resolve_dns': False,
            'telegram_api_reachable': False,
            'telegram_dcs_reachable': [],
            'firewall_status': 'Unknown',
            'recommendations': []
        }
        
        # Basic internet connectivity
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            results['internet_connected'] = True
        except Exception as e:
            results['recommendations'].append("No internet connection detected. Check your network settings.")
            results['error_details'] = str(e)
            # No need to continue if no internet
            return results
        
        # DNS resolution
        try:
            socket.gethostbyname("api.telegram.org")
            results['can_resolve_dns'] = True
        except:
            results['recommendations'].append("Cannot resolve Telegram domain names. Check your DNS settings.")
        
        # Telegram API reachability
        try:
            socket.create_connection(("api.telegram.org", 443), timeout=5)
            results['telegram_api_reachable'] = True
        except:
            results['recommendations'].append("Cannot connect to Telegram API. It may be blocked by your network/ISP.")
        
        # Telegram DCs reachability
        for i, (server, port) in enumerate(cls.TELEGRAM_SERVERS[1:], 1):
            try:
                socket.create_connection((server, port), timeout=5)
                results['telegram_dcs_reachable'].append(i)
            except:
                pass
        
        if not results['telegram_dcs_reachable']:
            results['recommendations'].append("Cannot connect to any Telegram data centers. This suggests blocking.")
        
        # Check Windows-specific issues
        if cls.is_windows():
            # Check Windows Firewall
            fw_check = cls.check_firewall_for_python()
            results['firewall_status'] = fw_check
            
            if fw_check.get('blocked', False):
                results['recommendations'].append(
                    "Windows Firewall appears to be blocking Python/Telegram connections. "
                    "Add python.exe to your firewall exceptions."
                )
            
            # Socket error detection for WinError 64
            if not results['telegram_api_reachable'] and not results['telegram_dcs_reachable']:
                results['recommendations'].append(
                    "You're experiencing the WinError 64 issue. Try the following:\n"
                    "1. Temporarily disable your antivirus/firewall\n"
                    "2. Try a different network connection (e.g., mobile hotspot)\n"
                    "3. Try a VPN service\n"
                    "4. Add Python to Windows Defender exceptions"
                )
        
        # General recommendations
        if results['internet_connected'] and not results['telegram_api_reachable']:
            results['recommendations'].append(
                "Your internet is working but Telegram appears to be blocked. "
                "This could be due to:\n"
                "1. Network/ISP blocking\n"
                "2. Firewall/Antivirus blocking\n"
                "3. VPN interference\n"
                "Try using a different network or a VPN service."
            )
        
        return results

# Run diagnostics when script is executed directly
if __name__ == "__main__":
    print("Windows Network Helper for Telegram Connections")
    print("=" * 50)
    
    if not WindowsNetworkHelper.is_windows():
        print("This tool is designed for Windows systems only.")
        sys.exit(1)
    
    print("Running network diagnostics...")
    results = WindowsNetworkHelper.run_network_diagnostics()
    
    print("\nResults:")
    print(f"- Internet Connection: {'✓' if results['internet_connected'] else '✗'}")
    print(f"- DNS Resolution: {'✓' if results['can_resolve_dns'] else '✗'}")
    print(f"- Telegram API: {'✓' if results['telegram_api_reachable'] else '✗'}")
    print(f"- Telegram DCs: {', '.join([f'DC{dc}' for dc in results['telegram_dcs_reachable']]) if results['telegram_dcs_reachable'] else '✗'}")
    
    print("\nRecommendations:")
    if not results['recommendations']:
        print("- All tests passed! Your connection to Telegram should be working.")
    else:
        for i, rec in enumerate(results['recommendations'], 1):
            print(f"{i}. {rec}")
    
    print("\nOptions:")
    print("1. Add Python to Windows Firewall exceptions (requires admin)")
    print("2. View Telegram status page")
    print("3. Exit")
    
    choice = input("\nEnter your choice (1-3): ")
    if choice == "1":
        if WindowsNetworkHelper.is_admin():
            if WindowsNetworkHelper.add_python_to_firewall():
                print("Successfully added Python to firewall exceptions!")
            else:
                print("Failed to add Python to firewall exceptions.")
        else:
            print("This action requires admin privileges. Please restart this script as administrator.")
    elif choice == "2":
        webbrowser.open("https://downdetector.com/status/telegram/")
