Models, evaluation, and results
===============================

Learning task
-------------

Input is a written movie review; the target is its positive or negative
sentiment label. This is binary text classification, not prediction of an IMDb
rating or a movie's box-office performance. Mixed or neutral opinions must
still receive one of the two supported labels.

TF-IDF turns review text into numeric features. Individual words and adjacent
word pairs can become features, up to a 50,000-feature vocabulary. A word pair
can retain a phrase such as "not good" that a single-word representation might
handle less clearly. The vectorizer learns vocabulary and IDF from training
data only.

Naive Bayes and Logistic Regression
-----------------------------------

Multinomial Naive Bayes estimates which class is more likely from the observed
text features, using a conditional-independence assumption. Smoothing
``alpha`` prevents a feature unseen in one class from producing a zero
likelihood. It is a useful fast baseline for sparse text features.

Logistic Regression learns a weight for each feature and converts their
combined score into a class probability. Despite its name, the implementation
here is a classifier. Its ``C`` hyperparameter controls the strength of
regularization. Both classifiers see the same TF-IDF representation and split.

Naive Bayes is the classifier being compared; Bayesian optimization is the
separate process that searches hyperparameters. TPE tuning does not turn
Logistic Regression into a Naive Bayes model.

Data split and measurement
--------------------------

The CSV contains 50,000 labeled reviews before cleaning. The October 19 tuned
run retained 49,582 reviews after removing missing rows and duplicate review
text. Its split contained 39,665 training reviews and 9,917 test reviews, using
stratification and random seed 42.

The tuning objective used three-fold cross-validation within training data.
Held-out test labels were excluded from hyperparameter selection. Once the
final test result is reported, repeatedly choosing future settings by that
same test score can bias the comparison. Further development should use
training-only validation and preserve a genuinely unseen final evaluation set.

Reported results
----------------

The baseline rows are the team's original reported evaluations. The tuned row
is the measured October 19 Celery run, which searched six Logistic Regression
settings. Values are rounded for display; consult the version's stored metrics
for full precision.

.. list-table:: Held-out test metrics
   :header-rows: 1

   * - Model
     - Accuracy
     - Macro F1
   * - Multinomial Naive Bayes baseline
     - 88.34%
     - 88.34%
   * - Logistic Regression baseline
     - 90.53%
     - 90.53%
   * - TPE-tuned Logistic Regression
     - 91.06%
     - 91.05%

The selected ``C`` was 8.102356207766633. Its training-only CV macro F1 was
0.907489478465694. The final held-out accuracy was 0.9105576283150146 and macro
F1 was 0.9105466225183032. The version ID was
``1b1e98fc-5fca-4d0c-98c8-52e459f772ce``. Numeric experiment IDs can differ
between the local database and the restored deployment.

The tuned run's training accuracy was 98.86% and training macro F1 was 98.86%.
The gap from its test scores suggests overfitting; a high training score alone
does not establish generalization. Baseline training-set scores were not
recorded in the original training output and should not be invented.

.. list-table:: Tuned run confusion matrix
   :header-rows: 1

   * - Actual label
     - Predicted negative
     - Predicted positive
   * - Negative
     - 4,460
     - 480
   * - Positive
     - 407
     - 4,570

Accuracy measures the proportion of correct predictions. Macro F1 calculates
F1 separately for each class and averages the two equally. A prediction's
displayed confidence is a model-estimated probability for that one review;
it is not measured test accuracy or a guarantee of correctness.

Limits of the conclusions
-------------------------

These results concern this dataset, preprocessing, and split. Sarcasm, very
short reviews, mixed opinions, and text unlike the training data can fail.
Probabilities have not been separately calibrated. The comparison does not
establish statistical significance or performance on an external dataset.

The displayed baseline-to-tuned accuracy change is about 0.53 percentage
points. Deployment-time reductions and reproducibility percentage gains were
not measured. Resume statements and presentation slides should use the actual
recorded scores and describe implemented features precisely.
