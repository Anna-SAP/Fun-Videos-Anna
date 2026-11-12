#!/bin/bash
# sheet.sh <dir> <first> <last> <step> <cols> <out.jpg>
d=$(realpath $1); a=$2; b=$3; st=$4; cols=$5; out=$6
list=$(mktemp -p "$(dirname $(realpath $6))"); for ((i=a;i<=b;i+=st)); do f=$(printf "%s/f%04d.jpg" $d $i); [ -f $f ] && echo "file '$f'" >> $list; done
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i $list -vf "scale=480:-1,drawtext=text='%{eif\:n*$st+$a\:d}':x=6:y=6:fontsize=18:fontcolor=yellow:box=1:boxcolor=black@0.6,tile=${cols}x$(( ( (b-a)/st + cols ) / cols )):padding=4:color=gray" -frames:v 1 $out
rm $list
