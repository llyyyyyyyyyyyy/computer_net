#!/bin/bash

SERVER_IP="10.117.40.1"
SERVER_PORT=12000
FILE_PATH="bomb2.tar"
TEST_RESULTS="test_results.csv"
CONGESTION="DelayBasedControl"  # Modify as needed
RELIABLE_TRANSMISSION="GBN"      # Modify as needed
TOTAL_TESTS=4
PACKET_LOSS_RATES=(0 5 10 20)    # Example packet loss rates in percent

# Create CSV for results
echo "Test No,Packet Loss Rate,Throughput (Bytes/sec),Utilization" > "$TEST_RESULTS"

for i in $(seq 1 $TOTAL_TESTS); do
  LOSS_RATE=${PACKET_LOSS_RATES[$i-1]}

  # Set up packet loss using `tc`
  sudo tc qdisc add dev ens33 root netem loss ${LOSS_RATE}%

  # Start time
  START_TIME=$(date +%s.%N)

  # Run client file transfer
  python3 client.py "$SERVER_IP" "$SERVER_PORT" "$FILE_PATH" "$CONGESTION"

  # End time
  END_TIME=$(date +%s.%N)

  # Calculate transfer duration
  DURATION=$(echo "$END_TIME - $START_TIME" | bc)
  
  # File size and retransmissions
  FILE_SIZE=$(stat -c%s "$FILE_PATH")
  TOTAL_SENT=$(grep -o 'Sent packet' log.txt | wc -l) # log client send messages to log.txt
  THROUGHPUT=$(echo "$FILE_SIZE / $DURATION" | bc)
  UTILIZATION=$(echo "scale=2; $FILE_SIZE / ($TOTAL_SENT * $BUFFER_SIZE)" | bc)

  echo "$i,$LOSS_RATE,$THROUGHPUT,$UTILIZATION" >> "$TEST_RESULTS"

  # Clear `tc` settings
  sudo tc qdisc del dev ens33 root netem
done

# Generate plot (requires matplotlib)
python3 -c "
import pandas as pd
import matplotlib.pyplot as plt

data = pd.read_csv('$TEST_RESULTS')
plt.figure(figsize=(10, 5))
plt.subplot(1, 2, 1)
plt.plot(data['Packet Loss Rate'], data['Throughput (Bytes/sec)'], marker='o')
plt.xlabel('Packet Loss Rate (%)')
plt.ylabel('Throughput (Bytes/sec)')
plt.title('Throughput vs Packet Loss Rate')

plt.subplot(1, 2, 2)
plt.plot(data['Packet Loss Rate'], data['Utilization'], marker='o', color='orange')
plt.xlabel('Packet Loss Rate (%)')
plt.ylabel('Utilization')
plt.title('Utilization vs Packet Loss Rate')

plt.tight_layout()
plt.savefig('test_results.png')
plt.show()
"
