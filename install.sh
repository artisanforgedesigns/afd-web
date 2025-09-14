sudo apt update
bash <(curl -L https://github.com/balena-io/wifi-connect/raw/master/scripts/raspbian-install.sh)
sudo apt install python3 python3-pip python3-venv
python3 -m venv myapp 
source myapp/bin/activate
pip install -r requirements.txt
sudo chmod +x wifi-connect.sh run.sh

# Add sudo crontab job
(sudo crontab -l 2>/dev/null; echo "@reboot sudo /home/pilock/wifi-connect.sh") | sudo crontab -

# Add non-sudo crontab job
(crontab -l 2>/dev/null; echo "@reboot /home/pilock/run.sh") | crontab -