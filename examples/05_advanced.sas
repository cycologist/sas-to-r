/* Advanced example: external files, GLM, MIXED, ordinal and multinomial models. */

data work.long;
    input id group $ time score y3 y4 count w;
    datalines;
1 A 1 10.2 1 1 2 1
1 A 2 11.0 1 2 3 2
1 A 3 11.5 2 2 4 3
2 A 1 9.8 1 1 2 1
2 A 2 10.7 2 3 3 2
2 A 3 11.1 2 3 4 3
3 A 1 12.0 2 1 3 1
3 A 2 12.6 2 2 4 2
3 A 3 13.0 3 2 5 3
4 A 1 10.5 1 2 2 1
4 A 2 11.2 1 3 3 2
4 A 3 11.9 2 3 4 3
5 B 1 13.1 2 1 4 1
5 B 2 13.8 3 2 5 2
5 B 3 14.2 3 2 6 3
6 B 1 12.7 2 2 4 1
6 B 2 13.4 2 3 5 2
6 B 3 14.0 3 3 6 3
7 B 1 14.3 3 1 5 1
7 B 2 14.9 3 2 6 2
7 B 3 15.4 3 3 7 3
8 B 1 13.5 2 2 4 1
8 B 2 14.1 2 3 5 2
8 B 3 14.8 3 3 6 3
;
run;

/* Write a CSV file with FILE and PUT. */
data _null_;
    set work.long;
    file 'examples/advanced_data.csv' dlm=',' dsd;
    put _all_;
run;

/* Read the CSV file back with INFILE and INPUT. */
data work.long_file;
    infile 'examples/advanced_data.csv' dlm=',' dsd;
    input id group $ time score y3 y4 count w;
run;

/* Fixed-effects ANOVA/regression with a classification variable. */
proc glm data=work.long_file;
    class group;
    model score = group time group*time / solution;
    means group;
    weight w;
run;

/* Random-intercept model for repeated measurements within id. */
proc mixed data=work.long_file method=reml;
    class id group;
    model score = group time group*time / solution;
    random intercept / subject=id type=un;
    weight w;
run;

/* Ordinal (proportional-odds) logistic regression. */
proc logistic data=work.long_file;
    class group;
    model y3 = group time / link=logit expb;
    weight w;
run;

/* Nominal multinomial logistic regression. */
proc logistic data=work.long_file;
    class group;
    model y4 = group time / link=glogit expb;
    weight w;
run;
