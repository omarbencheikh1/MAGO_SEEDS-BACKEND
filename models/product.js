const mongoose = require("mongoose");
const ProductSchema = new mongoose.Schema({
  name: {
    type: String,
    required: true
  },

  category: {
    type: String,
    required: true
  },

  image: {
    type: String
  },

  gallery: [
    {
      type: String
    }
  ],

  price: {
    type: Number,
  },

 

  oldPrice: {
    type: Number,
  },

  rating: {
    type: Number,
    min: 0,
    max: 5
  },
  content: {
    type: String
  },

  description: {
    type: String
  },

  shortDescription: {
    type: String
  },

  inStock: {
    type: Boolean,
    default: true
  },

  sku: {
    type: String
  },

  weight: {
    type: String
  },

  origin: {
    type: String
  },

  harvestPeriod: {
    type: String
  },

  sowingPeriod: {
    type: String
  },

  germination: {
    type: String
  },

  cultureTips: {
    type: String
  },

  specifications: [
    {
      label: String,
      value: String
    }
  ],
  
  type: {
  type: String, 
  enum: ['sweet', 'hot', 'none'], // 'none' for things that aren't peppers
  default: 'none'
}

});

module.exports = mongoose.model(
  "Product",
  ProductSchema
);