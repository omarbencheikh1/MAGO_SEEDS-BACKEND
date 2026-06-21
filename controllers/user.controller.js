const usermodel = require("../models/user.model");
const bcrypt = require("bcrypt");
const jwt = require("jsonwebtoken");
const User = require("../models/user.model");
const Order = require("../models/order.model");
const Review = require("../models/review.model");

module.exports.esmfct = async (req, res) => {
  try {
    res.status(200).json({ message: "User function called" });
  } catch (error) {
    res.status(500).json({ message: "Error occurred" });
  }
};

module.exports.getAllUsers = async (req, res) => {
  try {
    const users = await usermodel.find();
    res.status(200).json({ message: "User function called", users });
  } catch (error) {
    res
      .status(500)
      .json({ message: "Error fetching users", error: error.message });
  }
};

module.exports.addUserClient = async (req, res) => {
  try {
    const { email, password } = req.body;

    const hashedPassword = await bcrypt.hash(password, 10);

    const newUser = new usermodel({
      email,
      password: hashedPassword
    });
    await newUser.save();

    res.status(201).json({ message: "User added successfully", user: newUser });
  } catch (error) {
    res
      .status(500)
      .json({ message: "Error adding user", error: error.message });
  }
};

module.exports.addUserAdmin = async (req, res) => {
  try {
    const { email, password } = req.body;

    const newUser = new usermodel({ email, password, role: "admin" });
    await newUser.save();
    res
      .status(201)
      .json({ message: "Admin user added successfully", user: newUser });
  } catch (error) {
    res
      .status(500)
      .json({ message: "Error adding admin user", error: error.message });
  }
};

module.exports.deleteUser = async (req, res) => {
  try {
    const { id } = req.params;

    await usermodel.findByIdAndDelete(id);

    await Review.deleteMany({ user: id });

    res.status(200).json({ message: "User and associated reviews deleted successfully" });
  } catch (error) {
    res
      .status(500)
      .json({ message: "Error deleting user", error: error.message });
  }
};

module.exports.getUserById = async (req, res) => {
  try {
    const { id } = req.params;
    const user = await usermodel.findById(id);
    if (!user) {
      return res.status(404).json({ message: "User not found" });
    }
    res.status(200).json({ message: "User found", user });
  } catch (error) {
    res
      .status(500)
      .json({ message: "Error fetching user", error: error.message });
  }
};

module.exports.register = async (req, res) => {
  try {
    const { name, email, password, phone, avatar } = req.body;

    const existing = await User.findOne({ email });
    if (existing) {
      return res.status(400).json({ message: "Email already exists" });
    }

    const hashedPassword = await bcrypt.hash(password, 10);

    // AUTO-FILL AT REGISTRATION: Import profile details from their last guest order if available [1.1.2]
    let guestShippingData = {};
    try {
      const lastGuestOrder = await Order.findOne({ "customer.email": email }).sort({ createdAt: -1 });
      if (lastGuestOrder) {
        guestShippingData = {
          phone: lastGuestOrder.customer.phone || "",
          address: lastGuestOrder.shipping.address || "",
          city: lastGuestOrder.shipping.city || "",
          postalCode: lastGuestOrder.shipping.postalCode || ""
        };
      }
    } catch (orderErr) {
      console.log("No past guest orders found to auto-fill registration profiles", orderErr.message);
    }

    const user = new User({
      name,
      email,
      password: hashedPassword,
      role: "user",
      avatar,
      phone: phone || (guestShippingData.phone ? guestShippingData.phone : undefined),
      ...guestShippingData
    });

    await user.save();

    // AUTO-LINK PAST GUEST ORDERS: Automatically sync their past guest orders to their new profile ID [1.1.2]
    try {
      await Order.updateMany(
        { "customer.email": email, userId: { $exists: false } },
        { $set: { userId: user._id } }
      );
    } catch (linkErr) {
      console.log("Failed to sync past guest orders to new account:", linkErr.message);
    }

    res.status(201).json({ message: "User created" });

  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

module.exports.login = async (req, res) => {
  try {
    const { email, password } = req.body;

    const user = await User.findOne({ email });
    if (!user) return res.status(400).json({ message: "User not found" });

    const match = await bcrypt.compare(password, user.password);
    if (!match) return res.status(400).json({ message: "Wrong password" });

    const token = jwt.sign(
      { id: user._id, role: user.role },
      process.env.JWT_SECRET || "SECRET_KEY",
      { expiresIn: "1d" }
    );

    res.json({
      token,
      role: user.role,
      user: {
        name: user.name,
        email: user.email,
        avatar: user.avatar
      }
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

module.exports.isAdmin = (req, res, next) => {
  if (req.user.role !== "admin") {
    return res.status(403).json({ message: "Access denied" });
  }
  next();
};

module.exports.getCurrentUser = async (req, res) => {
  try {
    const user = await User.findById(req.user.id).select("-password");
    res.json(user);
  } catch (err) {
    res.status(500).json({
      error: err.message
    });
  }
};

module.exports.changeAvatar = async (req, res) => {
  try {
    const { avatar } = req.body;

    const user = await User.findByIdAndUpdate(
        req.user.id,
        { avatar },
        { new: true, runValidators: true } // Force validation on avatar update
      ).select("-password");

    res.json(user);
  } catch (err) {
    res.status(500).json({
      error: err.message
    });
  }
};

module.exports.getMyOrders = async (req, res) => {
  try {
    const user = await User.findById(req.user.id);
    if (!user) return res.status(404).json({ message: "User not found" });

    const orders = await Order.find({
      $or: [
        { userId: user._id },
        { "customer.email": user.email }
      ]
    }).sort({
      createdAt: -1
    });

    res.json(orders);
  } catch (err) {
    res.status(500).json({
      error: err.message
    });
  }
};

module.exports.getMyReviews = async (req, res) => {
  try {
    const reviews = await Review.find({
        user: req.user.id
      })
      .populate("product")
      .sort({
        createdAt: -1
      });

    res.json(reviews);
  } catch (err) {
    res.status(500).json({
      error: err.message
    });
  }
};

module.exports.updateSettings = async (req, res) => {
  try {
    const { name, phone, address, city, postalCode } = req.body;
    
    // Crucial: runValidators forces Mongoose to validate the phone number regex on edit [1.1.3]
    const user = await User.findByIdAndUpdate(
      req.user.id,
      { name, phone, address, city, postalCode },
      { new: true, runValidators: true } 
    ).select("-password");

    res.json(user);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

module.exports.updateUser = async (req, res) => {
  try {
    const { id } = req.params;
    // Crucial: runValidators forces validations during administrative user updates [1.1.3]
    const updatedUser = await User.findByIdAndUpdate(id, req.body, { new: true, runValidators: true });
    res.status(200).json({ message: "User updated successfully", user: updatedUser });
  } catch (error) {
    res.status(500).json({ message: "Error updating user", error: error.message });
  }
};