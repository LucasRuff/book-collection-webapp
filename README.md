This web app serves a simple Flask site for cataloging and managing a personal book collection. This project is only designed to run in a Unix-like environment (Linux and macOS).

After downloading, use 
```
export SECRET_KEY=$(openssl rand -hex 32)
```
one time to set a secret key for the server, and then
```
./run.sh
```
in your terminal to start the web app.

You will find the app running at http://127.0.0.1:5000
