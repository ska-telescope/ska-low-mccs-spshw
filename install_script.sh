#!/bin/bash

# Script for setting up development enviroment with docker, tango and other
# essentials that a developer will need to work on MCCS project
# Needs to be given a password for the sql server, the user should do well to
# make a note of this somewhere

sqlPassword="mypassword"

if [ $# -eq 0 ]
then
    echo "No sql password provided exiting"
    exit 1
else
    sqlPassword=$1
fi


# Install useful packages that most devs will need, git etc.
sudo apt install build-essential

# Install the requirements for docker and dockercli, add the current user as a user of docker
# so that they can access and use it
sudo apt install apt-transport-https ca-certificates curl gnupg-agent software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt-get update
sudo  apt install docker-ce docker-ce-cli
# You will need to log out and log back in before this user permissions change applies
sudo usermod -aG docker $USER


# Install background requirements for tango
sudo apt-get install g++ openjdk-8-jdk mariadb-server libmariadb-dev zlib1g-dev libomniorb4-dev libcos4-dev omniidl libzmq3-dev make

# Start the sql server
sudo service mariadb start

# Change the password to the one provided by the user
sudo mysql -e  "ALTER USER 'root'@'localhost' IDENTIFIED BY $sqlPassword;"

# Fetch and unpack the tango repo
cd ~
mkdir tango
cd tango
wget https://gitlab.com/api/v4/projects/24125890/packages/generic/TangoSourceDistribution/9.3.5/tango-9.3.5.tar.gz
tar xzvf tango-9.3.5.tar.gz
cd tango-9.3.5

# Configure, make and install tango
./configure --enable-java=yes --enable-mariadb=yes --enable-dbserver=yes --enable-dbcreate=yes --with-mysql-admin=root --with-mysql-admin-passwd=$sqlPassword --prefix=/usr/local/tango
make
sudo make install

# Add the sql password provided to tango to allow it to use the sql server
sudo sed "2 i export MYSQL_USER=root \nexport MYSQL_PASSWORD=$sqlPassword" /usr/local/tango/bin/tango

# Export tango host so it can be used by other programs
sudo echo 'export TANGO_HOST=localhost:10000' >> ~/.bashrc