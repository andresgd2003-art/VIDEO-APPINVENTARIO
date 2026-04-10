import paramiko, sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('148.230.82.14', username='root',
            key_filename=r'C:\Users\user\OneDrive\Escritorio\gemini cli\trader\trader_vps',
            timeout=30)

cmd = '''
cd /opt/trader
git pull origin master
echo "=== BUILD START ===" && docker build -t alpaca-trader:latest . 2>&1 | tail -5
docker rm -f alpaca-trader 2>/dev/null || true
docker run -d \
  --name alpaca-trader \
  --restart unless-stopped \
  --env-file /opt/trader/.env \
  -v /opt/trader/data:/app/data \
  -p 8000:8000 \
  alpaca-trader:latest
sleep 10
echo "=== ESTADO ==="
docker ps | grep alpaca-trader
echo "=== LOGS ==="
docker logs alpaca-trader --tail 20 2>&1
'''

stdin, stdout, stderr = ssh.exec_command(cmd, timeout=600)
print(stdout.read().decode('utf-8', errors='replace'))
ssh.close()
