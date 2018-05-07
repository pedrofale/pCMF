""" This file contains a class for inference of the parameters of the variational
distributions that approximate the posteriors of the Probabilistic Count Matrix Factorization
model.

The variational parameter updates were all derived from Equation (40) of Blei, D. et al 2016. 
Basically, each parameter of the variational approximation of some latent variable is set as 
the expected value of the natural parameter of that variable's complete conditional.
"""

import time
import math
import numpy as np
from scipy.special import digamma, factorial
from utils import log_likelihood, psi_inverse

class CoordinateAscentVI(object):
	def __init__(self, X, alpha, beta, pi):
		self.X = X
		self.N = X.shape[0] # no of observations
		self.P = X.shape[1] # no of genes
		self.K = alpha.shape[1] # latent space dim
		
		# Hyperparameters		
		self.alpha = np.expand_dims(alpha, axis=1).repeat(self.N, axis=1) # 2xNxK
		self.beta = beta # 2xPxK
		self.pi =  np.expand_dims(pi, axis=0).repeat(self.N, axis=0) # NxP
		self.logit_pi = np.log(self.pi / (1. - self.pi))

		# Variational parameters
		self.a = np.ones((2, self.N, self.K)) + np.random.rand(2, self.N, self.K)# parameters of q(U)
		self.b = np.ones((2, self.P, self.K)) + np.random.rand(2, self.P, self.K) # parameters of q(V)
		self.r = np.ones((self.N, self.P, self.K)) * 0.5 # parameters of q(Z)
		self.p = np.ones((self.N, self.P)) * 0.5 # parameters of q(D)

	def estimate_U(self, a):
		return a[0] / a[1]

	def estimate_V(self, b):
		return b[0] / b[1]

	def predictive_ll(self, X_test, n_iterations=10, S=100):
		""" Computes the average posterior predictive likelihood of data not used for 
		training: p(X_test | X). It uses the posterior parameter estimates and 
		Monte Carlo sampling to compute the integrals using S samples.
		"""
		N_test = X_test.shape[0]

		a = np.ones((2, N_test, self.K)) + np.random.rand(2, N_test, self.K)# parameters of q(U) for test data
		r = np.ones((N_test, self.P, self.K)) * 0.5 # parameters of q(Z) for test data
		p = np.ones((N_test, self.P)) * 0.5 # parameters of q(D) for test data

		# Posterior approximation over the local latent variables for each
		# of the new data points.
		for i in range(n_iterations):
			r = self.update_r(r, X_test, a, p) # parameter of Multinomial
			a = self.update_a(a, X_test, p, r) # parameters of Gamma
			p = self.update_p(p, X_test, a, r) # parameters of Bernoulli
		
		# # Monte Carlo estimation of the posterior predictive: use S samples
		# U_samples = sample_gamma(a[0], a[1], size=S) # S by X_test.shape[0] by K
		# D_samples = sample_bernoulli(p, size=S) # S by X_test.shape[0] by P
		# V_samples = sample_gamma(self.b[0], self.b[1], size=S) # SxPxK

		est_U = self.estimate_U(a)
		est_V = self.estimate_V(self.b)

		pred_ll = log_likelihood(X_test, est_U, est_V, p) # S
		pred_ll = np.mean(pred_ll)
			
		return pred_ll


	def update_a(self, a, X, p, r):
		""" Update the vector [a_1, a_2] for all (i,k) pairs.
		
		a_ik1 = alpha_k1 + sum_j(E[D_ij]*E[Z_ijk])
		a_ik2 = alpha_k2 + sum_j(E[D_ij]*E[V_jk])
		
		Requires:
		alpha	-- 1xK: the prior alphas vector
		p	-- NxP: E[D] vector
		X	-- NxP: the data
		r	-- NxPxK: E[Z]/X vector 
		b	-- PxK: parameters of q(V)
		"""
		N = X.shape[0]

		for i in range(N):
			for k in range(self.K):
				total1 = 0.
				total2 = 0.
				for j in range(self.P):
					total1 = total1 + p[i, j] * X[i, j] * r[i, j, k]
					total2 = total2 + p[i, j] * self.b[0, j, k] / self.b[1, j, k]
				a[0, i, k] = self.alpha[0, i, k] + total1
				a[1, i, k] = self.alpha[1, i, k] + total2

		return a

		#for j in range(self.P):
		#	total = total + np.expand_dims(self.p[:, j], 1) * np.matmul(np.expand_dims(self.X[:, j], 1).T, self.r[:, j, :])
		#self.a[0] = self.alpha[0] + total

		#self.a[1] = self.alpha[1] + np.matmul(self.p, self.b[0]/self.b[1])

	def update_b(self):
		""" Update the vector [b_1, b_2] for all (j,k) pairs.
		
		b_jk1 = beta_k1 + sum_i(E[D_ij]*E[Z_ijk])
		b_jk2 = beta_k2 + sum_i(E[D_ij]*E[U_ik])
		
		Requires:
		beta	-- the prior betas vector
		p	-- E[D] vector
		X	-- the data
		r	-- E[Z]/X vector
		a	-- parameters of q(U)
		"""

		for j in range(self.P):
			for k in range(self.K):
				total1 = 0.
				total2 = 0.
				for i in range(self.N):
					total1 = total1 + self.p[i, j] * self.X[i, j] * self.r[i, j, k]
					total2 = total2 + self.p[i, j] * self.a[0, i, k] / self.a[1, i, k]
				self.b[0, j, k] = self.beta[0, j, k] + total1
				self.b[1, j, k] = self.beta[1, j, k] + total2
		#total = 0.
		#for j in range(self.P):
		#	for k in range(self.K):
		#		for i in range(self.N):
		#			total = total + p[i, j] * X[i, j] * r[i, j, k]
		#for i in range(self.N):
		#	total = total + np.expand_dims(self.p[i, :], 1) * np.matmul(np.expand_dims(self.X[i, :], 1).T, self.r[i, :, :])
		#self.b[0] = self.beta[0] + total

		#self.b[1] = self.beta[1] + np.matmul(self.p.T, self.a[0]/self.a[1])

	def update_p(self, p, X, a, r):
		""" Update the vector p for all (i,j) pairs.
		
		logit(p_ij) = logit(pi_j) - sum_k(E[U_ik]*E[V_jk])
		
		Requires:
		pi	-- prior dropout probabilities
		a	-- parameters of q(U)
		b	-- parameters of q(V)
		"""
		N = X.shape[0]

		#logit_p = self.logit_pi - np.matmul(self.a[0]/self.a[1], (self.b[0]/self.b[1].T))
		logit_p = np.zeros((N, self.P))
		for i in range(N):
			for j in range(self.P):
				logit_p[i, j] = self.logit_pi[i, j] - np.sum(a[0, i, :]/a[1, i, :] * self.b[0, j, :]/self.b[1, j, :])
		p = np.exp(logit_p) / (1. + np.exp(logit_p))
		p[X != 0] = 1.

		return p

	def update_r(self, r, X, a, p):
		""" Update the vector r for all (i,j,k).
		
		r_ijk \prop exp(E[logU_ik] + E[logV_j)
		
		Note that, for X distributed as Gamma(a, b), E[logX] = digamma(a) - log(b)

		Requires:
		a	-- parameters of q(U)
		b	-- parameters of q(V)
		""" 
		N = X.shape[0]

		ar = digamma(a[0]) - np.log(a[1]) # NxK
		br = digamma(self.b[0]) - np.log(self.b[1]) # PxK
		aux = np.zeros((self.K,))	
		for i in range(N):
			for j in range(self.P):
				aux = np.exp(ar[i, :] + br[j, :])
				#for k in range(self.K):
				#	aux[k] = np.exp(a[i, k] + b[j, k])
				r[i, j,:] = aux / np.sum(aux)

		return r

	def update_pi(self):
		""" Empirical Bayes update of the hyperparameter pi
		"""
		# pi is NxP
		pi = np.mean(self.p, axis=0)

		self.pi = np.expand_dims(pi, axis=0).repeat(self.N, axis=0)
		self.logit_pi = np.log(self.pi / (1. - self.pi))

	def update_alpha(self):
		""" Empirical Bayes update of the hyperparameter alpha
		"""
		self.alpha[0] = np.log(self.alpha[1]) + np.expand_dims(np.mean(digamma(self.a[0]) - np.log(self.a[1]), axis=0), axis=0).repeat(self.N, axis=0)
		alpha_1 = self.alpha[0, 0, :]

		for k in range(self.K):
			alpha_1[k] = psi_inverse(2., self.alpha[0, 0, k])

		self.alpha[0] = np.expand_dims(alpha_1, axis=0).repeat(self.N, axis=0)
		self.alpha[1] = self.alpha[0] / np.mean(self.a[0] / self.a[1], axis=0)

	def update_beta(self):
		""" Empirical Bayes update of the hyperparameter beta
		"""
		self.beta[0] = np.log(self.beta[1]) + np.expand_dims(np.mean(digamma(self.b[0]) - np.log(self.b[1]), axis=0), axis=0).repeat(self.P, axis=0)
		beta_1 = self.beta[0, 0, :]

		for k in range(self.K):
			beta_1[k] = psi_inverse(2., self.beta[0, 0, k])

		self.beta[0] = np.expand_dims(beta_1, axis=0).repeat(self.P, axis=0)
		self.beta[1] = self.beta[0] / np.mean(self.b[0] / self.b[1], axis=0)

	def run_cavi(self, X_test=None, empirical_bayes=False, n_iterations=10, return_ll=True, sampling_rate=10, max_time=60, verbose=True):
		""" Run coordinate ascent variational inference and return 
		variational parameters.
		
		Get the log-likelihood every sampling_rate seconds.
		"""
		if return_ll:			
			ll_it = []
			ll_time = []

		# init clock
		start = time.time()
		init = start
		for it in range(n_iterations):
			# update the local variables
			self.a = self.update_a(self.a, self.X, self.p, self.r)
			self.p = self.update_p(self.p, self.X, self.a, self.r)
			self.r = self.update_r(self.r, self.X, self.a, self.p)

			# update global variables
			self.update_b()

			if empirical_bayes:
				# update hyperparameters
				self.update_pi()
				self.update_alpha()
				self.update_beta()
			
			if return_ll:
				# compute the LL
				if X_test is not None:
					ll_curr = self.predictive_ll(X_test)
				else:
					# subsample the data to evaluate the ll in
					idx = np.random.randint(self.N, size=100)
					est_U = self.estimate_U(self.a[:, idx, :])
					est_V = self.estimate_V(self.b)

					ll_curr = log_likelihood(self.X[idx], est_U, est_V, self.p[idx])
				end = time.time()
				it_time = end - start
				if it_time >= sampling_rate - 0.1*sampling_rate:
					ll_time.append(ll_curr)
					start = end
				ll_it.append(ll_curr)
				if verbose:
					if X_test is not None:
						print("Iteration {0}/{1}. Held-out log-likelihood: {2:.3f}. Elapsed: {3:.0f} seconds".format(it, n_iterations, ll_curr, end-init), end="\r")
					else:
						print("Iteration {0}/{1}. Log-likelihood: {2:.3f}. Elapsed: {3:.0f} seconds".format(it, n_iterations, ll_curr, end-init), end="\r")
				if (end - init) >= max_time:
					break
			elif verbose:
				print("Iteration {}/{}".format(it+1, n_iterations), end="\r")	
		if return_ll: 
			return ll_it, ll_time
