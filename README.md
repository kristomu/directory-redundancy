# directory-redundancy
This is a Python tool for finding subtrees of the file system (directories or
subdirectories) that are stored in multiple places on disk. It takes a file
containing a list of file sizes, hashes, and names; and outputs a report of the
form 

	./data/olddisk/Software/Video/* (13.00 GB, 10 items) is contained in:
		./data/Software/Video	(50.13 GB, 120 items)

which here means that all files inside ./data/olddisk/Software/Video can be
found (in the same location) within ./data/Software/Video.

Usage
-----

First create a listing file. This can be done by running something in the vein
of
	find /path/ -type f -exec ./sum_and_size.sh {} \; >listing.txt
The sum\_and\_size script will print the file it is investigating to stderr,
thus providing a progress report even with stdout piped to a listing file.
The sum\_and\_size script should be safe, but since it does touch every file
in the path provided when used in conjunction with find, you may want to run it
from a user with only read access if you want to be absolutely sure your files
won't be altered. (Or just examine the script).
sum\_and\_size requires sha224sum.

Second, run srec itself:
	python srec.py listing.txt

The computation should take something on the order of a few minutes (if you 
have lots of files).

Other notes
-----------

nameless\_srec is a version of srec that disregards file names when checking if
directories contain each other. However, in its current state, it is *extremely*
slow.

older/ contains older versions. I'm not entirely sure what cred does, while sred
is like srec but considerably slower.
