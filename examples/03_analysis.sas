/* Example 3: weighted correlation, PCA, linear regression, and CFA.
   The generated CFA call uses the lavaan package. */
data work.survey;
    input id x1 x2 x3 y w;
    datalines;
1 2.1 3.1 1.9 5.0 1.0
2 3.4 4.2 2.8 6.3 1.5
3 1.8 2.6 1.5 4.4 0.8
4 4.2 5.0 3.7 7.6 1.2
5 2.9 3.8 2.4 5.8 1.0
6 5.1 6.2 4.5 8.4 2.0
7 3.7 4.6 3.1 6.9 1.4
8 2.5 3.4 2.1 5.3 0.9
;
run;

proc corr data=work.survey;
    var x1 x2 x3 y;
    weight w;
run;

proc princomp data=work.survey cov;
    var x1 x2 x3;
    weight w;
run;

proc reg data=work.survey;
    model y = x1 x2 x3;
    weight w;
run;

proc calis data=work.survey;
    path F1 -> x1 x2 x3 y;
    weight w;
run;
