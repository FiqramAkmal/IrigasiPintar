import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
import joblib
import seaborn as sns
import matplotlib.pyplot as plt

df = pd.read_csv('DataFinalv1.csv')
print(df.shape)
print(df.dtypes)
print(df.isna().sum().sort_values(ascending=False).head(10))
print(df.describe(include='all').T)

TARGET = "label"

X = df[['precipitation', 'humidity', 'temperature']]
y = df[TARGET]

X_train, X_temp, y_train, y_temp = train_test_split(
    X, y, test_size=0.3, random_state=42, stratify=y
)
X_valid, X_test, y_valid, y_test = train_test_split(
    X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
)

numerical_cols = X.select_dtypes(include=["int64", "float64"]).columns.tolist()
categorical_cols = X.select_dtypes(include=["object", "category", "bool"]).columns.tolist()

num_pipeline = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("scaler", StandardScaler())
])

cat_pipeline = Pipeline([
    ("imputer", SimpleImputer(strategy="most_frequent")),
    ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
])

preprocessor = ColumnTransformer([
    ("num", num_pipeline, numerical_cols),
    ("cat", cat_pipeline, categorical_cols)
])

clf = Pipeline([
    ("preproc", preprocessor),
    ("model", RandomForestClassifier(random_state=42, n_jobs=-1))
])

param_grid = {
    "model__n_estimators": [100, 200],
    "model__max_depth": [None, 10, 30],
    "model__min_samples_leaf": [1, 3]
}

search = GridSearchCV(
    clf, param_grid, cv=5, scoring="accuracy", n_jobs=-1, verbose=1
)
search.fit(X_train, y_train)

print("Best params:", search.best_params_)
best_model = search.best_estimator_

y_val_pred = best_model.predict(X_valid)
print("Validation accuracy:", accuracy_score(y_valid, y_val_pred))
print(classification_report(y_valid, y_val_pred))

y_test_pred = best_model.predict(X_test)
print("Test accuracy:", accuracy_score(y_test, y_test_pred))
print(classification_report(y_test, y_test_pred))

cm = confusion_matrix(y_test, y_test_pred)
sns.heatmap(cm, annot=True, fmt="d", xticklabels=best_model.classes_, yticklabels=best_model.classes_, cmap="Blues")
plt.title(f"Confusion Matrix")
plt.xlabel("Predicted")
plt.ylabel("Actual")
plt.show()

MODEL_PATH = "WeatherAI.joblib"
joblib.dump(best_model, MODEL_PATH)
print("Model disimpan di:", MODEL_PATH)
