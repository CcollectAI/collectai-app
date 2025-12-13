CREATE OR REPLACE VIEW v_item_detail_full AS
SELECT
    i.id,
    i.name,
    i.category,
    i.estimated_value,
    i.change_1d,

    c.slug AS category_slug,
    c.label AS category_label,
    c.wave AS category_wave,
    c.active AS category_active,
    c.avg_value AS category_avg_value,
    c.item_count AS category_item_count,

    p.low AS pred_low,
    p.mid AS pred_mid,
    p.high AS pred_high,
    p.currency AS pred_currency,
    p.model_name AS pred_model,
    p.as_of AS pred_as_of,

    s.signals_json AS signals,

    i.created_at,
    i.updated_at,
    i.acquired_from,
    i.acquired_price,
    i.condition,
    i.edition,
    i.series
FROM items i
LEFT JOIN collectai_categories c
    ON c.slug = i.category
LEFT JOIN v_item_predictions p
    ON p.item_id = i.id
LEFT JOIN v_item_signals s
    ON s.item_id = i.id;
