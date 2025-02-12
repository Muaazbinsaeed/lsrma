## Subgroup Analysis of raw data categorical (binary: events/total)
# Load meta package.
library (meta)

# Load jsonlite package.
# This package is used to convert the analysis results in JSON format,
# which is used in the Python backend and visualization
library(jsonlite)

# For fixing the empty Rplot.pdf
pdf(NULL)

# Load data through readxl
# library(readxl)
# SUBGROUP_CAT_RAWDATA <- read_excel("C:/Users/sarsa/Desktop/Vitals/Research Stuff/MA/Studies/Living System/Code data_script/Data/SUBGROUP_CAT_RAWDATA.xlsx")
SUBGROUP_CAT_RAWDATA <- read.csv("{{ fn_csvfile }}")

# the meta package requires a specific data format with some attributes.


# We will use the function metabin to run the analysis
# some arguments (parameters) need to be set first
# model can be random-effects or fixed-effect (indicated with a logical)

# sm can be "OR", "RR", "RD"
# OR = Odds Ratio
# RR = Relative Risk
# RD = Risk Difference

# method can be "Inverse", "Peto", "MH"
# MH = Mantel-Haenszel
# Peto can only be indicated if model is fixed-effect and sm is OR

# method.tau can be "REML", "ML", "EB", "DL", "SJ", "HE", "HS", "PM"
# REML = Restricted Maximum-likelihood
#	ML = Maximum Likelihood
#	EB = Empirical Bayes
#	DL = DerSimonian-Laird
#	SJ = Sidik-Jonkman
#	HE = Hedges
#	HS = Hunter-Schmidt
#	PM = Paul-Mendel

# hakn can be used only if the model is random-effects (indicated with a logical)
# hakn = Hartung-Knapp adjustment

# running the analysis
subgroupresultsraw <- metabin(Et, 
                      Nt, 
                      Ec, 
                      Nc, 
                      data = SUBGROUP_CAT_RAWDATA, 
                      studlab = study, 
                      comb.fixed = {{ is_fixed }}, 
                      comb.random = {{ is_random }}, 
                      sm = "{{ measure_of_effect }}", 
                      method = "{{ pooling_method }}", 
                      method.tau = "{{ tau_estimation_method }}", 
                      hakn = {{ is_hakn }}, 
                      byvar = subgroup)

fig_width <- 10
fig_height <- fig_width * (0.25 + subgroupresultsraw$k * 0.06)
png(filename="{{ fn_outplt1 }}", width=fig_width, height=fig_height, units='in', res=200)
par(mar=c(1.5, 1, 1, 1))
leftcols_value <- "Favors {{ treatment }}"
rightcols_value <- "Favors {{ control }}"
{% if which_is_better == 'big' %}
    leftcols_value <- "Favors {{ control }}"
    rightcols_value <- "Favors {{ treatment }}"

{% endif %}

# generating the forest plot
forest.meta(subgroupresultsraw, 
            col.square = "black", 
            col.diamond = "red", 
            col.diamond.lines.{{ fixed_or_random }} = "black", 
            fontsize = 10, 
            squaresize = 0.5, 
            print.pval = TRUE, 
            lab.e = "{{ treatment }}", 
            lab.c = "{{ control }}", 
            pooled.totals = TRUE, 
            pooled.events = TRUE, 
            smlab = "{{ smlab_text }} (95% CI)", 
            weight.study = "same", 
            plotwidth = "8cm", 
            lwd = 1.8, 
            spacing = 1.3, 
            label.right = rightcols_value, 
            label.left = leftcols_value, 
            # colgap.forest.left = "1cm", 
            # colgap.forest.right = "0.1cm", 
            # colgap.left = "0.5cm", 
            leftcols = c("studlab", "event.e", "n.e", "event.c", "n.c", "effect", "ci"), 
            leftlabs = c("Events", "Total", "Events", "Total"), 
            rightcols = c("w.{{ fixed_or_random }}"), 
            rightlabs = c("Relative weight"), 
            col.study = "black", 
            test.subgroup.{{ fixed_or_random }} = TRUE, 
            col.by = "black")

dev.off()

# Merge all the results.
all_ret <- list(
    results = subgroupresultsraw,
    primma = subgroupresultsraw,
    version = list(
        jsonlite = packageVersion('jsonlite'),
        meta = packageVersion('meta')
    )
)

# Save results as json file!
jsonstr <- toJSON(all_ret, pretty=TRUE, force=TRUE)
cat(jsonstr, file = (con <- file("{{ fn_jsonret }}", "w", encoding = "UTF-8")))
close(con)
