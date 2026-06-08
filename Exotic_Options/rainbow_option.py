import math
import numpy as np


def MC_Rainbow(K,r,T,num_of_simulations,num_of_repetitions,num_of_assets,S,q,sigma,correlation):
    #Covariance matrix
    covariance_matrix = np.zeros((num_of_assets, num_of_assets))
    for i in range(num_of_assets):
        for j in range(num_of_assets):
            covariance_matrix[i][j] = correlation[i][j] * sigma[i] * sigma[j]

    #Cholesky algorithm
    def Cholesky_Decompostition(covariance_matrix):
        n = covariance_matrix.shape[0]
        A = np.zeros_like(covariance_matrix)
        #First row
        A[0][0] = math.sqrt(covariance_matrix[0][0])
        for i in range(1,n):
            A[0][i] = covariance_matrix[0][i]/A[0][0]
        #Sec and Thi row
        for i in range(1,n-1):
            A[i][i] = math.sqrt(covariance_matrix[i][i]-sum(A[k][i]**2 for k in range(i)))
            for j in range(i+1,n):
                A[i][j] = (1/A[i][i])*(covariance_matrix[i][j]-sum(A[k][i]*A[k][j] for k in range(i)))
        #Last row
        A[n-1][n-1] = math.sqrt(covariance_matrix[n-1][n-1]-sum(A[k][n-1]**2 for k in range(n-1)))
        return A
    
    A = Cholesky_Decompostition(covariance_matrix)
    np.random.seed(100)
    Z = np.random.standard_normal((num_of_repetitions, num_of_simulations, num_of_assets))
    Z_corr = Z @ A
    St = S*np.exp((r-q-0.5*sigma**2)*T + np.sqrt(T)*Z_corr)

     
    Call_payoff = np.maximum(np.max(St,axis = 2) - K, 0)
    C_batch_prices = np.exp(-r * T) * np.mean(Call_payoff, axis=1)
    MC_Call_price = np.mean(C_batch_prices)
    MC_C_se = np.std(C_batch_prices, ddof=1) 


        
    return MC_Call_price, MC_C_se
