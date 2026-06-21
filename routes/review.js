const express = require("express");
const router = express.Router();
const auth = require("../middleware/auth");
const { isAdmin } = require("../controllers/user.controller");
const upload = require("../middleware/upload");

const {
  createReview,
  getReviewsByProduct,
  canReviewProduct,
  deleteReview,
  voteReview,
  addReply,
  deleteReply, // Imported the new deleteReply controller function
  updateReview,
  updateReply,
  getAllReviews,
  syncAllRatings
} = require("../controllers/review.controller");

router.post(
  "/",
  auth,
  upload.array("images", 4),
  createReview
);

router.get(
  "/product/:productId",
  getReviewsByProduct
);

router.get(
  "/product/:productId/can-review",
  auth,
  canReviewProduct
);

router.delete(
  "/:id",
  auth,
  isAdmin,
  deleteReview
);

router.put('/:id/vote', auth, voteReview);
router.post('/:id/reply', auth, addReply); 
router.put('/:id', auth, upload.array("images", 4), updateReview);
router.put('/:id/reply/:replyId', auth, updateReply);

// Added secure route for deleting a reply
router.delete('/:id/reply/:replyId', auth, deleteReply);

router.get('/all', getAllReviews);
router.get("/sync-ratings", syncAllRatings);

module.exports = router;