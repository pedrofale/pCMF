"""
This script proves the importance of considering the model with zero-inflation for zero-inflated data.
We generate data with different levels of zero-inflation and cell type separability in the latent space.

We evaluate the latent space silhouette, the held-out log-likelihood and the imputation error of dropouts.
"""

from pCMF.misc import utils
from pCMF.models.pcmf.inferences import cavi_new

import numpy as np
from sklearn.decomposition import PCA, SparsePCA
from sklearn.metrics import silhouette_score, accuracy_score
from sklearn.model_selection import train_test_split
from scipy.stats import gamma

import time

import operator
import sys, os
import argparse
import json

def main():	
	init = time.time()

	newpath = './output'
	if not os.path.exists(newpath):
		print('Creating output directory...')
		os.makedirs(newpath)
		print('Done.\n')

	# Experiment parameters
	N = 100 # number of observations
	P = 1000 # observation space dimensionality
	K = 10 # latent space dimensionality
	C = 3 # number of clusters

	T = 60. * 10.
	Tm, Ts = divmod(T, 60)
	Th, Tm = divmod(Tm, 60)
	S = 10.
	max_iter = 1000000
	zero_prob = 0.5
	noisy_prop_arr = [0., 0.4, 0.7] # none, low, high noise
	eps_arr = [2., 10.] # low, high separability
	n_runs = 10 # number of experiments per setting

	param_dict = {'N': N, 'P': P, 'K': K, 'C': C, 'T': '{0:.0f}h{1:.0f}m{2:.0f}s'.format(Th, Tm, Ts), 'S' : S, 
				'max_iter': max_iter, 'zero_prob': zero_prob, 'noisy_prop_arr': noisy_prop_arr, 'eps_arr': eps_arr, 'n_runs': n_runs}
	print('Experiment parameters:')
	for param in param_dict:
	    print('{0}: {1}'.format(param, param_dict[param]))

	noisy_debug_strs = []
	for i in noisy_prop_arr:
		noisy_debug_strs.append('{}% noisy genes'.format(noisy_prop_arr[0]))
	eps_debug_strs = ['LOW separability', 'HIGH separability']

	silh_pca_scores = np.zeros((len(noisy_prop_arr), len(eps_arr), n_runs))
	silh_gap_scores = np.zeros((len(noisy_prop_arr), len(eps_arr), n_runs))
	silh_zigap_scores = np.zeros((len(noisy_prop_arr), len(eps_arr), n_runs))
	silh_szigap_scores = np.zeros((len(noisy_prop_arr), len(eps_arr), n_runs))

	dll_gap_scores = np.zeros((len(noisy_prop_arr), len(eps_arr), n_runs))
	dll_zigap_scores = np.zeros((len(noisy_prop_arr), len(eps_arr), n_runs))
	dll_szigap_scores = np.zeros((len(noisy_prop_arr), len(eps_arr), n_runs))

	holl_gap_scores = np.zeros((len(noisy_prop_arr), len(eps_arr), n_runs))
	holl_zigap_scores = np.zeros((len(noisy_prop_arr), len(eps_arr), n_runs))
	holl_szigap_scores = np.zeros((len(noisy_prop_arr), len(eps_arr), n_runs))

	dropid_zigap_scores = np.zeros((len(noisy_prop_arr) - 1, len(eps_arr), n_runs))
	dropid_szigap_scores = np.zeros((len(noisy_prop_arr) - 1, len(eps_arr), n_runs))

	dropimp_gap_scores = np.zeros((len(noisy_prop_arr) - 1, len(eps_arr), n_runs))
	dropimp_zigap_scores = np.zeros((len(noisy_prop_arr) - 1, len(eps_arr), n_runs))
	dropimp_szigap_scores = np.zeros((len(noisy_prop_arr) - 1, len(eps_arr), n_runs))

	for i in range(len(noisy_prop_arr)):
		print('\n--%s:' % noisy_debug_strs[i])
		for j in range(len(eps_arr)):
			print('\n\t--%s' % eps_debug_strs[j])
			for k in range(n_runs):
				# Generate data set
				Y, D, X, R, V, U, clusters = utils.generate_sparse_data(N, P, K, C=C, zero_prob=zero_prob, noisy_prop=noisy_prop_arr[i],
				                                             eps_U=eps_arr[j], return_all=True)
				Y_train, Y_test, X_train, X_test, D_train, D_test, U_train, U_test, c_train, c_test = train_test_split(Y, X, D, U.T, clusters, test_size=0.2, random_state=42)

				log_Y = np.log(1 + Y_train)

				# Run PCA
				print('PCA...')
				pca = PCA(n_components=K).fit_transform(log_Y)
				print('Done.\n')

				# Prior parameters
				alpha = np.abs(np.ones((2, K)) + np.random.rand(2, K))
				beta = np.abs(np.ones((2, P, K)) + np.random.rand(2, P, K))
				logit_pi_D = np.random.rand(P)
				pi_D = np.exp(logit_pi_D) / (1. + np.exp(logit_pi_D))
				logit_pi_S = np.random.rand(P)
				pi_S = np.exp(logit_pi_S) / (1. + np.exp(logit_pi_S))

				# Run GaP
				print('GaP:')
				infgap = cavi_new.CoordinateAscentVI(Y_train, alpha, beta, empirical_bayes=True)
				infgap.run(n_iterations=max_iter, calc_ll=False, calc_silh=False, clusters=c_train, sampling_rate=S, max_time=T)
				gap_U = infgap.a[0] / infgap.a[1] # VI estimate is the mean of the variational approximation
				gap_V = infgap.b[0] / infgap.b[1]
				gap_S = infgap.estimate_S(infgap.p_S)
				gap_D = infgap.estimate_D(infgap.p_D)
				print('Done.\n')

				# Run ZIGaP
				print('ZIGaP:')
				infzigap = cavi_new.CoordinateAscentVI(Y_train, alpha, beta, pi_D=pi_D, empirical_bayes=True)
				infzigap.run(n_iterations=max_iter, calc_ll=False, calc_silh=False, clusters=c_train, sampling_rate=S, max_time=T)
				zigap_U = infzigap.a[0] / infzigap.a[1] # VI estimate is the mean of the variational approximation
				zigap_V = infzigap.b[0] / infzigap.b[1]
				zigap_S = infzigap.estimate_S(infzigap.p_S)
				zigap_D = infzigap.estimate_D(infzigap.p_D)
				print('Done.\n')

				# Run SZIGaP
				print('SZIGaP:')
				infszigap = cavi_new.CoordinateAscentVI(Y_train, alpha, beta, pi_D=pi_D, pi_S=pi_S, empirical_bayes=True)
				infszigap.run(n_iterations=max_iter, calc_ll=False, calc_silh=False, clusters=c_train, sampling_rate=S, max_time=T)
				szigap_U = infszigap.a[0] / infszigap.a[1] # VI estimate is the mean of the variational approximation
				szigap_V = infszigap.b[0] / infszigap.b[1]
				szigap_S = infszigap.estimate_S(infszigap.p_S)
				szigap_D = infszigap.estimate_D(infszigap.p_D)
				print('Done.\n')

				print('Calculating silhouette scores...')
				# Calculate silhouette scores
				pca_silh = silhouette_score(pca, c_train)
				gap_silh = silhouette_score(gap_U, c_train)
				zigap_silh = silhouette_score(zigap_U, c_train)
				szigap_silh = silhouette_score(szigap_U, c_train)
				print('Done.\n')

				# Store silhs in array
				silh_pca_scores[i, j, k] = pca_silh
				silh_gap_scores[i, j, k] = gap_silh
				silh_zigap_scores[i, j, k] = zigap_silh
				silh_szigap_scores[i, j, k] = szigap_silh

				print('Calculating train data log-likelihood...')
				# Calculate train data log-likelihood
				gap_dll = utils.log_likelihood(Y_train, gap_U, gap_V, infgap.p_D, gap_S, clip=infgap.clip_ll)
				zigap_dll = utils.log_likelihood(Y_train, zigap_U, zigap_V, infzigap.p_D, zigap_S, clip=infzigap.clip_ll)
				szigap_dll = utils.log_likelihood(Y_train, szigap_U, szigap_V, infszigap.p_D, szigap_S, clip=infszigap.clip_ll)
				print('Done.\n')

				# Store dlls in array
				dll_gap_scores[i, j, k] = gap_dll
				dll_zigap_scores[i, j, k] = zigap_dll
				dll_szigap_scores[i, j, k] = szigap_dll

				print('Calculating held-out data log-likelihood...')
				# Calculate held-out data log-likelihood
				gap_holl = infgap.predictive_ll(Y_test)
				zigap_holl = infzigap.predictive_ll(Y_test)
				szigap_holl = infzigap.predictive_ll(Y_test)
				print('Done.\n')

				# Store holls in array
				holl_gap_scores[i, j, k] = gap_holl
				holl_zigap_scores[i, j, k] = zigap_holl
				holl_szigap_scores[i, j, k] = szigap_holl

				if i > 0:
					# Zero-Inflated data
					print('Calculating dropout identification accuracy...')
					# Calculate dropout identification accuracy
					dropout_idx = np.where(D_train == 0)
					zigap_acc = accuracy_score(zigap_D.flatten(), D_train.flatten())
					szigap_acc = accuracy_score(szigap_D.flatten(), D_train.flatten())
					print('Done.\n')

					# Store dropid in array
					dropid_zigap_scores[i-1, j, k] = zigap_acc
					dropid_szigap_scores[i-1, j, k] = szigap_acc

					print('Calculating dropout imputation error...')
					# Calculate dropout imputation error
					gap_R = np.dot(gap_U, gap_V.T)
					zigap_R = np.dot(zigap_U, zigap_V.T)
					szigap_R = np.dot(szigap_U, zigap_V.T)
					gap_err = utils.imputation_error(X_train, gap_R, dropout_idx)
					zigap_err = utils.imputation_error(X_train, zigap_R, dropout_idx)
					szigap_err = utils.imputation_error(X_train, szigap_R, dropout_idx)
					print('Done.\n')

					# Store dropimp in array
					dropimp_gap_scores[i-1, j, k] = gap_err
					dropimp_zigap_scores[i-1, j, k] = zigap_err
					dropimp_zigap_scores[i-1, j, k] = szigap_err

	print('Saving results to {0}...'.format(newpath))

	np.save('{0}/silh_pca_scores.npy'.format(newpath), silh_pca_scores)
	np.save('{0}/silh_gap_scores.npy'.format(newpath), silh_gap_scores)
	np.save('{0}/silh_zigap_scores.npy'.format(newpath), silh_zigap_scores)
	np.save('{0}/silh_szigap_scores.npy'.format(newpath), silh_szigap_scores)

	np.save('{0}/dll_gap_scores.npy'.format(newpath), dll_gap_scores)
	np.save('{0}/dll_zigap_scores.npy'.format(newpath), dll_zigap_scores)
	np.save('{0}/dll_szigap_scores.npy'.format(newpath), dll_szigap_scores)

	np.save('{0}/holl_gap_scores.npy'.format(newpath), holl_gap_scores)
	np.save('{0}/holl_zigap_scores.npy'.format(newpath), holl_zigap_scores)
	np.save('{0}/holl_szigap_scores.npy'.format(newpath), holl_szigap_scores)

	np.save('{0}/dropid_zigap_scores.npy'.format(newpath), dropid_zigap_scores)
	np.save('{0}/dropid_szigap_scores.npy'.format(newpath), dropid_szigap_scores)

	np.save('{0}/dropimp_gap_scores.npy'.format(newpath), dropimp_gap_scores)
	np.save('{0}/dropimp_zigap_scores.npy'.format(newpath), dropimp_zigap_scores)
	np.save('{0}/dropimp_szigap_scores.npy'.format(newpath), dropimp_szigap_scores)

	print('Done.\n')

	elapsed_sec = time.time() - init
	m, s = divmod(elapsed_sec, 60)
	h, m = divmod(m, 60)
	print('Script finished. Time elapsed: {0:.0f}h{1:.0f}m{2:.0f}s.'.format(h, m, s))

if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		sys.stderr.write("\nUser interrupt!\n")
		sys.exit(-1)