Training, tuning, and versioning
================================

Run a tracked baseline
----------------------

With the dataset in place, migrations applied, and the environment activated:

.. code-block:: powershell

   python train_and_track_tuning.py --model both

The script drops missing values and duplicate review text, makes a stratified
80/20 split with seed 42, and fits TF-IDF only on the training portion. It saves
both an experiment record and a new UUID-named model snapshot. The original
``train_models.py`` script is the simpler baseline trainer; it replaces the
two original files in ``models/`` instead of logging versioned experiments.

An experiment captures what was tried, and a model version identifies the
specific fitted pipeline produced by that run. Refresh the dashboard to load
new versions and click **Load Experiment Metrics** to compare their results.

Tune Logistic Regression
------------------------

.. code-block:: powershell

   python train_and_track_tuning.py --model logistic_regression --optimize --trials 6

Optuna's Tree-structured Parzen Estimator (TPE) searches for ``C``. The objective
is mean macro F1 from three stratified folds within the training set. TF-IDF
stays inside the pipeline for each fold, so validation-fold text is excluded
from vocabulary and IDF fitting. After selecting settings, the script fits on
the full training portion and evaluates on the held-out test portion.

Larger ``C`` means weaker regularization in Logistic Regression. It allows a
closer fit to training data and can increase overfitting. The search tests this
tradeoff using cross-validation rather than assuming a larger value is better.
For Naive Bayes, the corresponding tuning command searches its smoothing
parameter ``alpha``:

.. code-block:: powershell

   python train_and_track_tuning.py --model naive_bayes --optimize --trials 6

The script records the trials, selected settings, training-only CV score,
dataset hash, split hashes, package versions, final metrics, and model-file
hash. Matching inputs, split settings, and dependency versions supports
reproduction; it does not establish a measured percentage improvement in
"reproducibility."

Run tuning in the background
----------------------------

Open a separate PowerShell terminal and leave the worker running:

.. code-block:: powershell

   cd C:\Users\elige\hardyboys-ml-project
   .\.venv\Scripts\Activate.ps1
   python background_jobs.py worker

In another activated terminal at the same project root:

.. code-block:: powershell

   python background_jobs.py enqueue --model logistic_regression --trials 6

The command returns a job ID immediately. Copy it into a status command, for
example replacing ``YOUR_JOB_ID`` here with the returned UUID:

.. code-block:: powershell

   python background_jobs.py status YOUR_JOB_ID

The local broker uses the filesystem and stores task results in SQLite under
``local_jobs/``. Worker and client processes must share that directory. This is
a demonstrated local background job, not a hosted distributed worker. A Render
worker on another machine would need a shared broker, database configuration,
and model-artifact storage.

Publish a selected version
--------------------------

Copy the desired UUID from the registry or training output:

.. code-block:: powershell

   python publish_model.py export YOUR_VERSION_ID

This creates ``published_models/<version-id>/model.joblib`` and
``manifest.json``. The manifest retains settings, provenance, measured metrics,
and a checksum. Commit the selected bundle and deploy it. The deployment build
runs:

.. code-block:: powershell

   python publish_model.py restore

Restore verifies the checksum and recreates the model snapshot and records.
Runtime snapshots under ``models/versions/`` are ignored by Git; selected
published bundles are intentionally committed. Publish only artifacts your
team generated or otherwise trusts, because joblib loading deserializes Python
objects.
