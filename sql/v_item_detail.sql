CREATE OR REPLACE VIEW v_item_detail AS
SELECT
  id,
  name,
  category,
  estimated_value,
  change_1d
FROM items;
