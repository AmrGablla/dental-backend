# ML Models Directory

This directory contains machine learning models used for dental scan analysis and processing.

## Structure

```
models/
├── trained/          # Pre-trained model files
├── configs/          # Model configuration files
├── scripts/          # Training and evaluation scripts
└── data/             # Training and validation datasets
```

## Model Types

- **Mesh Quality Assessment**: Models for detecting defects and quality issues in 3D scans
- **Anatomical Segmentation**: Models for identifying dental structures
- **Format Conversion**: Models for optimizing mesh conversion between formats

## Usage

Models are loaded and used by the worker service for processing dental scans. Each model should include:

- Model file (weights/checkpoints)
- Configuration file
- Version information
- Performance metrics
- Training dataset information

## Security

All models must be validated for:
- No embedded malicious code
- Proper licensing
- HIPAA/GDPR compliance
- Data privacy considerations
