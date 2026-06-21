const Order = require("../models/order.model");
const Review = require("../models/review.model");
const User = require("../models/user.model");
const Product = require("../models/product");
const mongoose = require("mongoose");

const updateProductAverageRating = async (productId) => {
    const reviews = await Review.find({ product: productId });
    
    if (reviews.length === 0) {
        await Product.findByIdAndUpdate(productId, { rating: 0 });
        return;
    }

    const totalRating = reviews.reduce((sum, review) => sum + review.rating, 0);
    const avgRating = totalRating / reviews.length;
    
    await Product.findByIdAndUpdate(productId, { rating: avgRating });
};

exports.createReview = async (req, res) => {
    try {
        const { productId, rating, title, comment, pros, cons, recommend } = req.body;
        const user = await User.findById(req.user.id);

        const deliveredOrder = await Order.findOne({
            "customer.email": user.email,
            status: "delivered",
            "items.productId": new mongoose.Types.ObjectId(productId)
        });

        if (!deliveredOrder) {
            return res.status(403).json({ message: "Only delivered customers can review" });
        }

        const existingReview = await Review.findOne({
            product: productId,
            user: req.user.id
        });

        if (existingReview) {
            return res.status(400).json({ message: "You already reviewed this product" });
        }

        const location = deliveredOrder.shipping?.city ? `${deliveredOrder.shipping.city}` : "Unknown Location";

        const review = new Review({
            product: productId,
            user: req.user.id,
            order: deliveredOrder._id,
            rating,
            title,
            comment,
            pros,
            cons,
            recommend: recommend === 'true',
            location,
            images: req.files ? req.files.map((file) => `/uploads/${file.filename}`) : []
        });

        await review.save();
        await updateProductAverageRating(productId);
        res.status(201).json(review);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

exports.getReviewsByProduct = async (req, res) => {
    try {
        const sort = req.query.sort || "date";
        let sortOption = {};

        if (sort === "date") sortOption = { createdAt: -1 };
        if (sort === "rating") sortOption = { rating: -1 };
        if (sort === "helpful") sortOption = { helpful: -1 };

        const reviews = await Review.find({ product: req.params.productId })
            .populate("user", "name avatar role")
            .populate("replies.user", "name avatar role")
            .sort(sortOption);

        res.json(reviews);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

exports.voteReview = async (req, res) => {
    try {
        const review = await Review.findById(req.params.id);
        if (!review) return res.status(404).json({ message: "Review not found" });

        const userId = req.user.id;
        const { type } = req.body;

        const hasUpvoted = review.upvotedBy.some(id => id.toString() === userId.toString());
        const hasDownvoted = review.downvotedBy.some(id => id.toString() === userId.toString());

        review.upvotedBy = review.upvotedBy.filter(id => id.toString() !== userId.toString());
        review.downvotedBy = review.downvotedBy.filter(id => id.toString() !== userId.toString());

        if (type === 'up' && !hasUpvoted) {
            review.upvotedBy.push(userId);
        }
        if (type === 'down' && !hasDownvoted) {
            review.downvotedBy.push(userId);
        }

        review.helpful = review.upvotedBy.length;
        review.unhelpful = review.downvotedBy.length;

        await review.save();
        res.json(review);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

exports.addReply = async (req, res) => {
    try {
        const review = await Review.findById(req.params.id);
        if (!review) return res.status(404).json({ message: "Review not found" });

        review.replies.push({
            user: req.user.id,
            text: req.body.text
        });

        await review.save();
        res.json(review);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

exports.canReviewProduct = async (req, res) => {
    try {
        const productId = req.params.productId;
        const user = await User.findById(req.user.id);

        if (!user) {
            return res.json({ canReview: false });
        }

        const deliveredOrder = await Order.findOne({
            "customer.email": user.email,
            status: "delivered",
            items: {
                $elemMatch: {
                    productId: new mongoose.Types.ObjectId(productId)
                }
            }
        });

        if (!deliveredOrder) {
            return res.json({ canReview: false });
        }

        const existingReview = await Review.findOne({
            product: productId,
            user: user._id
        });

        if (existingReview) {
            return res.json({ canReview: false });
        }

        res.json({ canReview: true });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

exports.deleteReview = async (req, res) => {
    try {
        const review = await Review.findById(req.params.id);
        if (!review) return res.status(404).json({ message: "Review not found" });

        const productId = review.product;

        await Review.findByIdAndDelete(req.params.id);
        await updateProductAverageRating(productId); 

        res.json({ message: "Review deleted successfully" });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

exports.updateReview = async (req, res) => {
    try {
        const review = await Review.findById(req.params.id);
        if (!review) return res.status(404).json({ message: "Review not found" });

        if (review.user.toString() !== req.user.id) {
            return res.status(403).json({ message: "Not authorized to edit this review" });
        }

        review.comment = req.body.comment || review.comment;
        review.pros = req.body.pros || "";
        review.cons = req.body.cons || "";

        let existingImages = req.body.existingImages || [];
        if (typeof existingImages === "string") existingImages = [existingImages];

        const newFiles = req.files ? req.files.map(f => `/uploads/${f.filename}`) : [];
        review.images = [...existingImages, ...newFiles];

        await review.save();
        await updateProductAverageRating(review.product);
        res.json(review);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

exports.updateReply = async (req, res) => {
    try {
        const review = await Review.findById(req.params.id);
        if (!review) return res.status(404).json({ message: "Review not found" });

        const reply = review.replies.find(r => r._id.toString() === req.params.replyId);
        if (!reply) return res.status(404).json({ message: "Reply not found" });

        if (reply.user.toString() !== req.user.id && req.user.role !== 'admin') {
            return res.status(403).json({ message: "Not authorized to edit this reply" });
        }

        reply.text = req.body.text;
        await review.save();
        res.json(review);
    } catch (err) {
        console.log("Reply Edit Error:", err);
        res.status(500).json({ error: err.message });
    }
};

// Added Controller logic for deleting a reply from a review safely
exports.deleteReply = async (req, res) => {
    try {
        const review = await Review.findById(req.params.id);
        if (!review) return res.status(404).json({ message: "Review not found" });

        const reply = review.replies.id(req.params.replyId);
        if (!reply) return res.status(404).json({ message: "Reply not found" });

        // Ensure authorization: Only original replier OR an admin can delete
        if (reply.user.toString() !== req.user.id && req.user.role !== 'admin') {
            return res.status(403).json({ message: "Not authorized to delete this reply" });
        }

        // Pull the subdocument from array and save
        review.replies.pull(req.params.replyId);
        await review.save();
        res.json(review);
    } catch (err) {
        console.log("Reply Delete Error:", err);
        res.status(500).json({ error: err.message });
    }
};

exports.getAllReviews = async (req, res) => {
    try {
        const reviews = await Review.find()
            .populate("user", "name avatar")
            .populate("product", "name image")
            .sort({ rating: -1, createdAt: -1 })
            .limit(8);
            
        res.json(reviews);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

exports.syncAllRatings = async (req, res) => {
    try {
        const products = await Product.find();
        
        for (let product of products) {
            await updateProductAverageRating(product._id);
        }
        
        res.json({ message: "SUCCESS! All product ratings have been recalculated and fixed." });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};