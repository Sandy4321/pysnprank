#!/usr/bin/env python
# SNPrank - single nucleotide polymorphism (SNP) ranking algorithm

# Uses a GAIN file, together with a damping factor gamma, 
# (default is .85), to compute SNPrank scores.
# Prints a series of rows containing the SNP name, SNPrank score,
# information gain, sorted in descending order by SNPrank.
#
# Authors:  Brett McKinney <brett.mckinney@gmail.com>
#           Nick Davis <nick@nickdavis.name> 
#           Ahwan Pandey <ahwan-pandey@utulsa.edu>  
#           Chris Johnson <chris-johnson@utulsa.edu>
from __future__ import division
from numpy import *
import sys, csv, optparse

def normalize(xs):
	"""Normalize a numpy array"""
	return xs/sum(xs)

class SNPrank:
	"""Provides functions for running SNPrank algorithm on a GAIN matrix"""
	def __init__(self, infilename):
		"""Initialize SNPrank object with GAIN file object"""

		reader = csv.reader(infilename, delimiter="\t")
		
		# The first row is the SNP labels
		self.SNPs = reader.next()
		
		self.GAIN = array([row for row in reader], dtype=float64)
	
	def calculate_snprank(self, gamma, usegpu):
		"""Runs the SNPrank algorithm on the input data, using gamma as the damping factor.
		   usegpu enables GPU computing (using the CUDAMat library) for the matrix multiplication.
		   Returns the SNPrank scores and diagonal (main effect) of original GAIN matrix."""

		# A GAIN matrix is an NxN matrix
		m,n = self.GAIN.shape
		if m != n:
			raise ValueError("Input is not an NxN matrix")

		# Vector of column sums
		colsum = self.GAIN.sum(axis=0)
		
		# Get indices of c vector that are not zero
		colsum_nzidx = colsum.nonzero()[0]
		
		D = zeros((n,n))
		T_nz = ones(n)
		
		# Where a column doesn't sum to 0, the diagonal in D
		# ought to be the reciprocal of the column sum.
		# Likewize T_nz ought to be 1-gamma rather than 1.
		for i in colsum_nzidx:
			D[i][i] = 1/colsum[i]
			T_nz[i] = 1 - gamma
	
		T = zeros((n,n))
		if usegpu:
			import cudamat as cm	
			# initialize CUDAMat
			cm.init()
			
			# Copy GAIN and D matrices to GPU
			G_gpu = cm.CUDAMatrix(self.GAIN)
			D_gpu = cm.CUDAMatrix(D)
			
			# Do matrix multiplication on the GPU
			GD_prod = cm.dot(G_gpu,D_gpu)

			# Transition matrix
			T = (gamma * GD_prod.asarray() ) + (self.GAIN.diagonal().reshape(n,1) * T_nz) / self.GAIN.trace()
		else:
			# Transition matrix
			T = (gamma * dot(self.GAIN,D) ) + (self.GAIN.diagonal().reshape(n,1) * T_nz) / self.GAIN.trace()
		
		# r is an arbitrary vector, which we initialize to 1/n
		r = (ones(n)).reshape(n,1)/n;
		
		# Cutoff for matrix convergence
		threshold = 10**(-4)
		
		# Multiply r by T until r converges to within the threshold
		while True:
			r_old, r = r, normalize(dot(T,r))
			if all( abs(r-r_old) < threshold ):
				break
		        
		return r.reshape(1,n)[0], self.GAIN.diagonal()
	
	def print_to_file(self, SNPs, snp_rank, ig, output):
        	"""Output table of SNP names, SNPranks, information gain, and degree to a file."""
		writer = csv.writer(output,delimiter='\t')
		
		sort_temp = sorted(zip(SNPs, snp_rank, ig), key=lambda item:item[1], reverse =True)
		
		writer.writerow(['SNP','SNPrank','IG'])
		map(output.write,("%s\t%.6f\t%.6f\n" % tuple(vals) for vals in sort_temp))

def main():
	# Create option parser
	parser = optparse.OptionParser(usage="%prog [OPTIONS]", version="%prog 0.1")
	# Add options to parser; use defaults if none specified
	parser.add_option("-i", "--input", dest="infile", help="read data from INFILE")
	parser.add_option("-o", "--output", dest="outfile", help="output to OUTFILE")
	parser.add_option("-g", "--gamma", dest="gamma", help="gamma value (default: .85)", default=.85)
	parser.add_option("-n", "--gpu", action="store_true", dest="usegpu", help="enable GPU", default=False)
	
	(options, args) = parser.parse_args()
	
	# Check to see if filenames are mentioned, open to r/w if not
	try:
		infile  = open(options.infile,  'r') if options.infile  else sys.stdin
	except IOError as err:
		if err.errno != 2:
			raise err
		print "Error: Input file could not be opened."
		parser.print_help()
		return 1

	try:
		outfile = open(options.outfile, 'w') if options.outfile else sys.stdout
	except IOError as err:
		if err.errno != 2:
			raise err
		print "Error: Output file could not be opened."
		parser.print_help()
		return 1
	
	# Create data object from class
	full_data = SNPrank(infile)
	
	infile.close()
	
	# Get SNPrank and information gain from calculate_snprank
	snprank, IG = full_data.calculate_snprank(float(options.gamma), options.usegpu)
	
	# Print to file
	full_data.print_to_file(full_data.SNPs,snprank, IG, outfile)
	
	outfile.close()
	return 0
        
if __name__ == "__main__":
	sys.exit(main())
