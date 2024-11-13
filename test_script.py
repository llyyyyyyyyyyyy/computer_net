#!/bin/bash

SERVER_IP="192.168.11.1"
SERVER_PORT=12000
FILE_PATH="bomb2.tar"
TEST_RESULTS="test_results.csv"
CONGESTION="DelayBasedControl"  # Modify as needed
RELIABLE_TRANSMISSION="GBN"      # Modify as needed
TOTAL_TESTS=6
PACKET_LOSS_RATES=(10 20 30 40 50 60)    # Example packet loss rates in percent



for i in $(seq 1 $TOTAL_TESTS); do
  LOSS_RATE=${PACKET_LOSS_RATES[$i-1]}

  # Set up packet loss using `tc`
  sudo tc qdisc add dev ens33 root netem loss ${LOSS_RATE}%


  # Run client file transfer
  python3 client.py "$SERVER_IP" "$SERVER_PORT" "$FILE_PATH" "$CONGESTION"


  # Clear `tc` settings
  sudo tc qdisc del dev ens33 root netem
done

