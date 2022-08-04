#!/bin/bash

cd data/drone-tracking-datasets/dataset4/detections/

for i in 0 1 2 3 4 5 6; do
    wget https://raw.githubusercontent.com/CenekAlbl/drone-tracking-datasets/master/dataset4/detections/cam${i}.txt
    # wget https://raw.githubusercontent.com/CenekAlbl/drone-tracking-datasets/master/dataset4/detections/cam0.txt
    # wget https://raw.githubusercontent.com/CenekAlbl/drone-tracking-datasets/master/dataset4/detections/cam0.txt
    # wget https://raw.githubusercontent.com/CenekAlbl/drone-tracking-datasets/master/dataset4/detections/cam0.txt
    # wget https://raw.githubusercontent.com/CenekAlbl/drone-tracking-datasets/master/dataset4/detections/cam0.txt
    # wget https://raw.githubusercontent.com/CenekAlbl/drone-tracking-datasets/master/dataset4/detections/cam0.txt
done
cd -