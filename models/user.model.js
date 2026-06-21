const mongoose = require("mongoose");

const userSchema = new mongoose.Schema({
  name: { type: String, required: true },
  email: { 
    type: String, 
    required: true, 
    unique: true,
    match: [/^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$/, "Please provide a valid email"]
  },
  password: { 
    type: String, 
    required: true,
    minlength: [6, "Password must be at least 6 characters long"]
  },
  avatar: {type: String, default: "carrot.png"},
  role: { type: String, enum: ["user", "admin"], default: "user" },
  phone: { 
    type: String, 
    default: "",
    validate: {
      validator: function(v) {
        // Allows empty strings for optional signup profiles, but validates if a phone is entered
        return v === "" || /^[2-5789][0-9]{7}$/.test(v);
      },
      message: "Please provide a valid Tunisian phone number (8 digits)"
    }
  },
  address: { type: String, default: "" },
  city: { type: String, default: "" },
  postalCode: { type: String, default: "" }
}, {
  timestamps: true // Added timestamps for tracking creation date
});

module.exports = mongoose.model("User", userSchema);