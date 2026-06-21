const mongoose = require("mongoose");

const orderSchema = new mongoose.Schema(
  {
    userId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: false // Optional to support guest checkouts
    },

    customer: {
      name: { type: String, required: true },
      email: { 
        type: String, 
        required: true,
        match: [/^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$/, "Please provide a valid email"]
      },
      phone: { 
        type: String, 
        required: true,
        match: [/^[2-5789][0-9]{7}$/, "Please provide a valid Tunisian phone number (8 digits)"]
      }
    },

    shipping: {
      address: { type: String, required: true },
      city: { type: String, required: true },
      postalCode: { type: String, required: true },
      notes: String
    },

    items: [
      {
        productId: {
          type: mongoose.Schema.Types.ObjectId,
          ref: "Product",
          required: true
        },
        name: { type: String, required: true },
        image: String,
        price: { type: Number, required: true, min: 0 },
        quantity: { type: Number, required: true, min: 1 }
      }
    ],

    subtotal: { type: Number, required: true, min: 0 },

    shippingFee: {
      type: Number,
      default: 7,
      min: 0
    },

    total: { type: Number, required: true, min: 0 },

    paymentMethod: {
      type: String,
      default: "Cash on Delivery"
    },

    status: {
      type: String,
      enum: [
        "pending",
        "confirmed",
        "shipped",
        "delivered",
        "cancelled"
      ],
      default: "pending"
    }
  },
  {
    timestamps: true
  }
);

// Safety hook to guarantee orders cannot be saved empty
orderSchema.pre('save', function(next) {
  if (this.items.length === 0) {
    next(new Error('Order must contain at least one item'));
  } else {
    next();
  }
});

module.exports = mongoose.model(
  "Order",
  orderSchema
);