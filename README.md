A extension to the PrePost algorithm described by Yates et al. (http://core.kmi.open.ac.uk/download/pdf/5224046.pdf).
The algorithm discovers static preconditions by querying Google for documents and creates feature vectors in order to
learn a classifier for the static preconditions. The learning process used Radial Basis Function Kernel Support Vector Machines.
The implementation is partial and to be used in conjunction with the LOCM algorithm, which generate domain models from partially
observed action sequences, much like this implementation is intended to do.