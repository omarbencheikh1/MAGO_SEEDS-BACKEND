const Order = require("../models/order.model");
const Product = require("../models/product");
const jwt = require("jsonwebtoken");

exports.createOrder = async (req, res) => {
  try {
    const items = req.body.items;

    const authHeader = req.headers.authorization;
    if (authHeader && authHeader.startsWith("Bearer ")) {
      try {
        const token = authHeader.replace("Bearer ", "");
        const decoded = jwt.verify(token, process.env.JWT_SECRET || "SECRET_KEY");
        req.body.userId = decoded.id || decoded._id;
      } catch (tokenErr) {
        console.log("Optional checkout token verification failed, checking out as guest...", tokenErr.message);
      }
    }

    // CHECK EACH PRODUCT
    for (const item of items) {
      const product = await Product.findById(item.productId);

      if (!product) {
        return res.status(404).json({
          message: `${item.name} not found`
        });
      }

      if (!product.inStock) {
        return res.status(400).json({
          message: `${product.name} is out of stock`
        });
      }
    }

    // CREATE ORDER
    const order = new Order(req.body);
    await order.save();

    res.status(201).json(order);

  } catch (err) {
    res.status(500).json({
      error: err.message
    });
  }
};

exports.getAllOrders = async (req, res) => {
  try {
    const orders = await Order.find().populate("userId", "name email");
    res.json(orders);
  } catch (err) {
    res.status(500).json({
      error: err.message
    });
  }
};

exports.getOrderById = async (req, res) => {
  try {
    const order = await Order.findById(req.params.id).populate("userId", "name email");

    if (!order) {
      return res.status(404).json({
        message: "Order not found"
      });
    }

    res.json(order);

  } catch (err) {
    res.status(500).json({
      error: err.message
    });
  }
};

exports.updateOrder = async (req, res) => {
  try {
    // Crucial: runValidators forces database checks on order edits (such as phone edits) [1.1.3]
    const updatedOrder = await Order.findByIdAndUpdate(
        req.params.id,
        req.body,
        {
          new: true,
          runValidators: true
        }
      );

    if (!updatedOrder) {
      return res.status(404).json({
        message: "Order not found"
      });
    }

    res.json(updatedOrder);

  } catch (err) {
    res.status(500).json({
      error: err.message
    });
  }
};

exports.deleteOrder = async (req, res) => {
  try {
    const deletedOrder = await Order.findByIdAndDelete(req.params.id);

    if (!deletedOrder) {
      return res.status(404).json({
        message: "Order not found"
      });
    }

    res.json({
      message: "Order deleted successfully"
    });

  } catch (err) {
    res.status(500).json({
      error: err.message
    });
  }
};