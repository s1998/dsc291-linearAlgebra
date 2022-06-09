# dsc291-linearAlgebra


To run the baselines related to linear algebra, use the notebook  `matrixfactorization_notebook.ipynb` 
The notebook has been properly commented and divided into sections for explaining everything. 

To run the transformers based models, use the file `transformersTrain.py`. 
It runs the code on the given datasets. The file has been commented to provide appropriate pointers.
Also, the logs for the same are present oin twitterCovidKaggleLogs.

Experiemtal results obtained :

|   Method name  | Micro-F1 | Macro-F1 | Weighted-F1 |
|:--------------:|:--------:|:--------:|:-----------:|
| Sparse Vectors |   0.547  |   0.557  |    0.547    |
|       LSA      |   0.376  |   0.369  |    0.369    |
|      NNMF      |   0.350  |   0.334  |    0.339    |
|      BERT      |   0.858  |   0.853  |    0.858    |


Environment assumes the following:

sentence-transformers==1.2.0 <br />
transformers==3.5.1 <br />
scikit-image==0.17.2 <br />
scikit-learn==0.23.2 <br />
numpy==1.19.5 <br />
pandas==1.1.5 <br />
