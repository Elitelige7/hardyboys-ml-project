MLFlowPro project handbook
==========================

MLFlowPro helps a machine learning engineer train, compare, save, and use
movie-review sentiment models. The demo classifies review text as positive or
negative using TF-IDF with Naive Bayes or Logistic Regression. Django stores
experiment settings, measured results, and model-version metadata.

This handbook describes the HardyBoys implementation. It distinguishes the
deployed web demo, the local training worker, and features that need additional
configuration. The original assignment describes a broader product vision.

Live application: https://hardyboys-ml-project.onrender.com/

Repository: https://github.com/Elitelige7/hardyboys-ml-project

.. toctree::
   :maxdepth: 2

   setup
   architecture
   experiments
   api
   evaluation
   deployment

Start here
----------

* To run the demo locally, follow :doc:`setup`.
* To understand what each component does, read :doc:`architecture`.
* To train or tune a model, follow :doc:`experiments`.
* To explain the measured scores, use :doc:`evaluation`.

Team
----

Elige Diallo, Elijah Sow, and Kasaan Dornelus. Individual responsibilities and
contributions should be recorded in the repository README and supported by each
member's own commits.
