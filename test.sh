#!/bin/bash

./test_server.py &
sleep 0.2

if [ "$1" = "-v" ]; then
    ./bot.py test_config.yml
else
    ./bot.py test_config.yml &> /dev/null
fi
