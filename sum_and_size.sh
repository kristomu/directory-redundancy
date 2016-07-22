>&2 echo "Now trying $*"
#SIZE=`du "$*" |sed "s/\t.*//g"`
APPSIZE=`du --apparent-size -B 1 "$*" |tr "\t" "\n" |head -n 1`
SIZE=`du -B 1 "$*" |tr "\t" "\n" |head -n 1`
SUM=`sha224sum "$*"`
if [ "$SUM" != "" ]
then
	echo "$APPSIZE    $SIZE   $SUM"
fi
