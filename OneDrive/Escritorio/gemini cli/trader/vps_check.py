import paramiko, sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('148.230.82.14', username='root', key_filename=r'C:\Users\user\OneDrive\Escritorio\gemini cli\trader\trader_vps', timeout=15)

cmd = '''
docker exec alpaca-trader python -c "
import requests, os, datetime
url = 'https://paper-api.alpaca.markets/v2/account/portfolio/history'
headers = {'APCA-API-KEY-ID': os.environ.get('ALPACA_API_KEY'), 'APCA-API-SECRET-KEY': os.environ.get('ALPACA_SECRET_KEY')}
res = requests.get(url, headers=headers, params={'period': '1D', 'timeframe': '5Min'})
data = res.json()
print('Last timestamp Normal:', datetime.datetime.fromtimestamp(data['timestamp'][-1]).strftime('%Y-%m-%d %H:%M') if data.get('timestamp') else 'None')

res_ext = requests.get(url, headers=headers, params={'period': '1D', 'timeframe': '5Min', 'extended_hours': 'true'})
data_ext = res_ext.json()
print('Last timestamp Extended:', datetime.datetime.fromtimestamp(data_ext['timestamp'][-1]).strftime('%Y-%m-%d %H:%M') if data_ext.get('timestamp') else 'None')
"
'''
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
print("TEST:", stdout.read().decode('utf-8'))
sys.exit(0)
