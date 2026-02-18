This web app serves a simple Flask site for cataloging and managing a personal book collection. This project is only designed to run in a Unix-like environment (Linux and macOS).

## Local run (manual)

After downloading, create a secret key and run the app:

```
export SECRET_KEY=$(openssl rand -hex 32)
./run.sh
```

You will find the app running at http://127.0.0.1:5000

## Run as a systemd service (Raspberry Pi / Linux)

These steps make the app start automatically on boot and restart if it crashes.

1) Make sure the script is executable:

```
chmod +x /home/pi/Library/run.sh
```

2) Create an environment file for secrets and runtime config:

```
cat <<'EOF' > /home/pi/Library/.env
SECRET_KEY=your_real_secret_here
FLASK_DEBUG=0
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
EOF
```

3) Create the systemd unit file:

```
sudo tee /etc/systemd/system/bookcollection.service > /dev/null <<'EOF'
[Unit]
Description=Book Collection Flask App
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/Library
EnvironmentFile=/home/pi/Library/.env
ExecStart=/home/pi/Library/run.sh
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

4) Enable and start the service:

```
sudo systemctl daemon-reload
sudo systemctl enable bookcollection
sudo systemctl start bookcollection
```

5) Check status and logs:

```
sudo systemctl status bookcollection
journalctl -u bookcollection -f
```

The app will be available at http://<pi-ip>:5000
