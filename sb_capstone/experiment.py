import joblib
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import classification_report

def train_receive_offer(data, file):
    y = data.purchased
    X = data.drop(columns=["purchased"])

    X_train, X_test, y_train, y_test = train_test_split(X, y)

    clf = KNeighborsClassifier(n_neighbors=5, algorithm="kd_tree", leaf_size=10)
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    score = classification_report(y_test, y_pred, zero_division=True, output_dict=True)

    joblib.dump(clf, file)

    return file, score

def train_select_offer(data, file):
    y_cols = np.arange(1, 11).astype(str).tolist()

    y = data[y_cols]
    X = data[data.columns[~data.columns.isin(y_cols)]]

    X_train, X_test, y_train, y_test = train_test_split(X, y)

    clf = MultiOutputClassifier(
        KNeighborsClassifier(n_neighbors=5, algorithm="kd_tree", leaf_size=10)
    )

    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    score = classification_report(y_test, y_pred, zero_division=True, output_dict=True)

    joblib.dump(clf, file)

    return file, score