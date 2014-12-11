#!/bin/bash

while true; do
killall python
killall libqatemcontrol
python rmsgraph.py
sleep 5
done
