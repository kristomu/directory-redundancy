# Subset Redundancy: finds redundant directories in a directory structure
# given by a hash (md5sum etc) output file. Redundant directories are ones
# that are contained in another directory, i.e. if for all a in x/, y/a also
# exists, then x is redundant wrt y.

# Slow and probably very wasteful, but hey, I got da (CPU) power.

# {A forest-growing approach might be better.}

import md5, sys
from collections import defaultdict

if len(sys.argv) < 2:
	print "Usage:", sys.argv[0], "sumandsizelist.txt"
	print "\twhere sumandsizelist.txt is a file list in sum and size format."
	print
	print "\tE.g.", sys.argv[0], "test.txt"
	sys.exit(-1)

infile_fn = sys.argv[1]
infiles = [infile_fn]	# TODO: Support more files?

#infile_fn = "test.txt"
#infile_fn = "/home/km/morediskmd5s.txt"

#infiles = ["/home/km/morediskmd5s.txt", "/home/km/laptophomemd5s.txt", "/home/km/homemd5s.txt"]
#infiles = ["/home/km/laptophomemd5s.txt"]

#infiles = ["/home/km/optdisk3.txt"]	# optdisksum segfaults Python! WTF?

def sxor(s1,s2):    
    #https://stackoverflow.com/questions/2612720/how-to-do-bitwise-exclusive-or-of-two-strings-in-python
    return ''.join(chr(ord(a) ^ ord(b)) for a,b in zip(s1,s2))

def get_fn_hash(new_filename, new_hash):
	new_hash = md5.new(new_filename + new_hash)
	return new_hash.digest()

tree_sets_dict = defaultdict(set)
tree_count_dict = defaultdict(int)
hash_file_size = {}

occurs_where = defaultdict(list)

# TODO: get total number of lines?
for infile_fn in infiles:
	totcount = 0
	period = 0
	for line in open(infile_fn, "r"):
		if period == 10000:
			sys.stderr.write("%d      \n" % totcount)
		        sys.stderr.flush()
			period = 0
		period += 1
		totcount += 1

		# Split by space
		try:
			#filesize, file_hash, filename = line.split(None, 2)
			app_file_size, real_file_size, file_hash, filename = line.split(None, 3)
			filesize = int(real_file_size)
			#filesize = 1
			#file_hash, filename = line.split(None, 2)
			#print line
			#print filename
		except ValueError:
			continue

		# For every possible way to split the directory into a / b,
		# put the fn hash of b into the set corresponding to the string
		# a in the dictionary.

		for pos in xrange(len(filename)):
			if filename[pos] == "/":
				tree_to_add_to = filename[:pos+1]
				filename_within_tree = filename[pos+1:]

				fn_hash = get_fn_hash(filename_within_tree, file_hash)

				tree_sets_dict[tree_to_add_to].add(fn_hash)
				occurs_where[fn_hash].append(tree_to_add_to)

				try:
					tree_count_dict[tree_to_add_to] += int(filesize) #1
					hash_file_size[fn_hash] = int(filesize)
				except ValueError:
					tree_count_dict[tree_to_add_to] += 1
					hash_file_size[fn_hash] = 1

# Find the hashes that occur more than once, then check if there's a
# redundancy relation between any of the directories named there.
# This will give the wrong results if there's a hash collision, but
# I don't think we'll see any of those.

already_checked_pairs = {}
found_contained = {}
identicals = {}
i = 0

total_occurrences = float(len(occurs_where)-1)

for fn_hash in occurs_where:
	sys.stderr.write("%.4f    \r" % (i/total_occurrences))
	sys.stderr.flush()
	i += 1
	
	# How imperative!
	if len(occurs_where[fn_hash]) < 2:
		continue

	collision_candidates = occurs_where[fn_hash]
	for x in xrange(len(collision_candidates)):
		x_cand = collision_candidates[x]
		x_set = tree_sets_dict[x_cand]
		x_set_len = len(x_set)

		for y in xrange(x):
			y_cand = collision_candidates[y]
			if (x_cand, y_cand) in already_checked_pairs:
				continue
			if not (tree_sets_dict[y_cand].issubset(x_set) or 
				x_set.issubset(tree_sets_dict[y_cand])):
					continue

			y_set = tree_sets_dict[y_cand]
			y_set_len = len(y_set)
			
			xy_intersect_set = x_set.intersection(y_set)
			xy_intersect_len = len(xy_intersect_set)

			intersection_files_size = sum([hash_file_size[x] for x in xy_intersect_set])

			if xy_intersect_len == x_set_len:
				found_contained[(x_cand, y_cand, intersection_files_size)] = True
				already_checked_pairs[(x_cand, y_cand)] = True
			if xy_intersect_len == y_set_len:
				found_contained[(y_cand, x_cand, intersection_files_size)] = True
				already_checked_pairs[(y_cand, x_cand)] = True

			if xy_intersect_len == x_set_len and xy_intersect_len == y_set_len:
				if x_cand < y_cand:
					identicals[(x_cand, y_cand, intersection_files_size)] = True
				else:
					identicals[(y_cand, x_cand, intersection_files_size)] = True


# Now we work in a pretty similar way to cred. Sort the contained-in data in
# a list by total file size. Then print them after pruning (pruning comes later).
# For the pruning algorithm, see cred.

contained_pairs_by_size = [x for x in found_contained]
contained_pairs_by_size.sort(key=lambda x: len(x[1]))
contained_pairs_by_size.sort(key=lambda x: x[2], reverse=True)

# Seen this before...
# 3.

already_seen = {}

def where_seen_before(seen_before_dict, directory):
	for char_pos in xrange(len(directory)):
		if directory[-char_pos-1] == '/':
			if directory[:-char_pos] in seen_before_dict:
				return seen_before_dict[directory[:-char_pos]]
	return None

def has_seen_all_before(seen_before_dict, list_of_dirs):
	seen_before_indices = {}

	for directory in list_of_dirs:
		seen_before_idx = where_seen_before(seen_before_dict, directory)
		if seen_before_idx != None:
			seen_before_indices[seen_before_idx] = True
	
	return len(seen_before_indices) == len(list_of_dirs)

seen_idx = 0

print

for contained_pair in contained_pairs_by_size:
	if not has_seen_all_before(already_seen, contained_pair[:2]):
		if contained_pair in identicals or (contained_pair[1], contained_pair[0],
			contained_pair[2]) in identicals:
			print contained_pair, "IDENTICAL"
		else:
			print contained_pair
		for directory in contained_pair[:2]:
			already_seen[directory] = seen_idx
			seen_idx += 1
