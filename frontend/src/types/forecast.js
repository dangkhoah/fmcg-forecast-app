/**
 * @typedef {Object} ForecastData
 * @property {string} id
 * @property {string} [name]
 * @property {string} dataset_id
 * @property {string} dataset_name
 * @property {number} dataset_row_count
 * @property {string[]} dates
 * @property {number[]} values
 * @property {number[]} [lower_bound]
 * @property {number[]} [upper_bound]
 * @property {Array<{date: string, product_id: number, outlet_id: number, prediction: number}>} [detailed_records]
 * @property {string} created_at
 * @property {Object} parameters
 * @property {boolean} cached
 * @property {number} [training_time]
 * @property {string} [detected_freq]
 * @property {number} [mape]
 */

// This export statement makes the file a module, allowing the JSDoc types to be imported.
export {};
