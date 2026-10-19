/* Example 4: categorical data analysis.
   Crosstab, chi-square independence test, and logistic regression. */
data work.customers;
    input id age income group $ churn;
    datalines;
1 25 32000 Basic 0
2 31 41000 Basic 0
3 47 62000 Basic 1
4 52 71000 Basic 1
5 23 28000 Basic 0
6 38 52000 Basic 0
7 29 36000 Basic 1
8 35 45000 Basic 0
9 44 58000 Basic 1
10 56 76000 Basic 1
11 27 33000 Basic 0
12 39 50000 Basic 0
13 33 47000 Premium 1
14 41 64000 Premium 1
15 50 82000 Premium 0
16 58 91000 Premium 1
17 36 55000 Premium 0
18 45 69000 Premium 1
19 28 38000 Premium 1
20 40 60000 Premium 0
21 48 72000 Premium 1
22 54 85000 Premium 1
23 32 44000 Premium 0
24 37 53000 Premium 1
;
run;

proc freq data=work.customers;
    tables group * churn / chisq expected row;
run;

proc logistic data=work.customers;
    class group / param=ref;
    model churn(event='1') = age income group / expb;
run;
