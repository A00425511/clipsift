# ClipSift V6 – Model and Validation Comparison

## Model Checkpoint

Both implementations use identical pre-trained RF-DETR Small weights.

SHA-256:
da078e3cbd7120f5e1880c66723b21e62acad7260adddc4ac7f32fe1468aa49a

V6 did not retrain or fine-tune the model.

## Validation Configuration

- Bounding-box matching threshold: IoU >= 0.50
- One-to-one matching between predictions and annotations
- Evaluation based on small, manually annotated development samples

## V6 Validation Results

| Dataset | Precision | Recall |
|---|---:|---:|
| First 10 frames | 27.3% | 83.3% |
| Second 10 frames | 25.4% | 94.4% |

## Important Limitations

These are preliminary development-sample results, not independent benchmark results.

The same model weights do not guarantee identical predictions because the two applications use different processing pipelines.

A fair comparison requires a shared test dataset, consistent annotation rules, and identical evaluation settings.

The human tagging protocol and IoU-based detection evaluation measure different things.

## Next Steps

1. Use IoU 0.50 consistently for V6 validation.
2. Agree on a shared annotation and evaluation protocol.
3. Evaluate both pipelines on the same independently labeled video frames.
4. Compare precision, recall, processing time, and review workload.
