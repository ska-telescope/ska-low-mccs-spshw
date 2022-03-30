#!/bin/bash
# docker image required by this script
# >docker pull think/plantuml

SOURCE_CODE_DIR=../../src/ska_low_mccs
DOCS_SOURCE_DIR=../src/api

FILES="antenna/antenna_device.py \
       apiu/apiu_device.py \
       cluster_manager/cluster_manager_device.py \
       controller/controller_device.py \
       subrack/subrack_device.py \
       tile/tile_device.py \
       subarray.py \
       subarray_beam.py \
       station_beam.py \
       station.py"

convert () {
	file=$1
	base=`basename "${file}"`
	echo $base 
    uml_file=${base/.py/_class_diagram.uml}
    echo $uml_file
    python3 generate_uml_class_diagrams.py -n -o ${DOCS_SOURCE_DIR}/${uml_file} ${SOURCE_CODE_DIR}/${file}
 
    svg_file=${base/.py/_class_diagram.svg}
    cat ${DOCS_SOURCE_DIR}/${uml_file} | docker run --rm -i think/plantuml >${DOCS_SOURCE_DIR}/${svg_file}
}

for f in ${FILES}; do convert $f; done


to_svg() {
    cat ${DOCS_SOURCE_DIR}/antenna_device.uml | docker run --rm -i think/plantuml >${DOCS_SOURCE_DIR}/antenna_device.svg
}