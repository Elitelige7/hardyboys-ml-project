# HardyBoys-ml-project
Machine learning project by the HardyBoys team:

Elijah Sow,
Elige Diallo,
Kasaan Dornelus


MLFlow Pro: Movie Reviewer


## Model Evaluation

The project evaluates two machine-learning models for movie-review sentiment
classification: Multinomial Naive Bayes and Logistic Regression. Both models use TF-IDF vectorization to convert text reviews into numerical features. The dataset was divided into 80% training data and 20% testing data. The split used stratified sampling and a random seed of 42.

### Evaluation Results

| Model | Accuracy | Macro F1 Score |
|---|---:|---:|
| Multinomial Naive Bayes | 88.28% | 88.28% |
| Logistic Regression | 90.49% | 90.49% |

### Findings

Logistic Regression achieved the best results with an accuracy and a macro F1 score of 90.49%, while Naive Bayes achieved an accuracy and macro F1 score of 88.28%. These results indicate that Logistic Regression performed better on the test dataset, the prediction script currently uses the Logistic Regression model to classify individual movie reviews. Both models were also tested with six manually selected reviews that they both
produced identical predictions for all six examples. Correctly classifying
the clearly positive and negative reviews, but they both classified two
neutral reviews as negative. Since the models are trained for binary
positive vs negative classification, they do not have a separate neutral
sentiment category. The six manual tests provide a qualitative check, while the accuracy and
macro F1 scores provide quantitative evaluation on the test dataset.
