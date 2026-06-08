import numpy as np
import math
import sys
#BS and CRR pls construct by urself


# Bisection method
def Bisection(S, K, r, q, T, market_price_option, n, an, bn):
     
     function_bs_call = lambda sigma: BS(S, K, r, q, sigma, T)[0] - market_price_option
     function_bs_put = lambda sigma: BS(S,K,r,q,sigma,T)[1] - market_price_option

     function_crr_european_call = lambda sigma: CRR(S, K, r, q, sigma, T, n, option_type='European')[0] - market_price_option
     function_crr_european_put = lambda sigma: CRR(S, K, r, q, sigma, T, n, option_type='European')[1] - market_price_option 

     function_crr_american_call = lambda sigma: CRR(S, K, r, q, sigma, T, n, option_type='American')[0] - market_price_option    
     function_crr_american_put = lambda sigma: CRR(S, K, r, q, sigma, T, n, option_type='American')[1] - market_price_option

     def bisection_loop(f, label):
        a, b = an, bn   
        for i in range(1000):
            if abs(f(a)) < 0.0000001 or abs(f(b)) < 0.0000001:
                print(f"Implied Volatility for {label}:", a if abs(f(a)) < 0.0000001 else b)
                break
            if f(a) * f(b) < 0:
                x_n = a + (b - a) / 2
                if f(a) * f(x_n) < 0:
                    b = x_n
                else:
                    a = x_n
            else:
                print(f"{label} f(an)f(bn) >= 0")
                break

     bisection_loop(function_bs_call, "BS Call")
     bisection_loop(function_bs_put, "BS Put")
     bisection_loop(function_crr_european_call, "CRR European Call")
     bisection_loop(function_crr_european_put,  "CRR European Put")
     bisection_loop(function_crr_american_call, "CRR American Call")
     bisection_loop(function_crr_american_put,  "CRR American Put")

# Newton's method
def Newtons(S, K, r, q, T, market_price_option, n, initial_guess,convergence_criterion):
    function_bs_call = lambda sigma: BS(S, K, r, q, sigma, T)[0] - market_price_option
    function_bs_put = lambda sigma: BS(S,K,r,q,sigma,T)[1] - market_price_option

    function_crr_european_call = lambda sigma: CRR(S, K, r, q, sigma, T, n, option_type='European')[0] - market_price_option
    function_crr_european_put = lambda sigma: CRR(S, K, r, q, sigma, T, n, option_type='European')[1] - market_price_option 

    function_crr_american_call = lambda sigma: CRR(S, K, r, q, sigma, T, n, option_type='American')[0] - market_price_option    
    function_crr_american_put = lambda sigma: CRR(S, K, r, q, sigma, T, n, option_type='American')[1] - market_price_option

    def newton_loop(f,label):
        x_n = initial_guess
        for i in range(1000):
            f_prime = (f(x_n + 0.00001) - f(x_n)) / 0.00001
            if f_prime == 0:
                print(f"{label} Derivative is zero. No solution found.")
                return
            x_n1 = x_n - f(x_n) / f_prime
            if abs(f(x_n1)) < convergence_criterion:
                print(f"Implied Volatility for {label}:", x_n1)
                return
            x_n = x_n1
        print(f"{label} Did not converge within the maximum number of iterations.")

    newton_loop(function_bs_call,"BS Call")
    newton_loop(function_bs_put,"BS Put")
    newton_loop(function_crr_european_call,"CRR European Call")
    newton_loop(function_crr_european_put,"CRR European Put")
    newton_loop(function_crr_american_call,"CRR American Call")
    newton_loop(function_crr_american_put,"CRR American Put")
