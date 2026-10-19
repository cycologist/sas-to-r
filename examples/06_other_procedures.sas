/* Other common analysis procedures: TTEST, NPAR1WAY, ANOVA, and GENMOD. */

data work.scores;
    input id group $ sex $ score before after count;
    datalines;
1 A M 78 70 72 2
2 A F 82 75 79 3
3 A M 75 68 71 2
4 A F 88 80 85 4
5 A M 80 73 77 3
6 A F 85 78 80 4
7 B F 90 84 87 5
8 B M 92 86 91 6
9 B F 87 81 85 4
10 B M 94 88 90 6
11 B F 89 83 86 5
12 B M 91 85 90 6
13 C M 98 92 96 7
14 C F 95 89 91 6
15 C M 99 93 96 8
16 C F 96 90 95 7
17 C M 97 91 95 7
18 C F 100 94 96 8
;
run;

/* Two-sample and paired t tests. */
proc ttest data=work.scores h0=0 sides=2;
    class sex;
    var score;
    paired before*after;
run;

/* Wilcoxon rank-sum for two groups, Kruskal-Wallis for more than two. */
proc npar1way data=work.scores wilcoxon;
    class group;
    var score;
run;

/* One-way ANOVA; PROC ANOVA is handled like a simple PROC GLM. */
proc anova data=work.scores;
    class group;
    model score = group;
    means group;
run;

/* Generalized linear model with a Poisson distribution and log link. */
proc genmod data=work.scores;
    class group;
    model count = group score / dist=poisson link=log;
run;
