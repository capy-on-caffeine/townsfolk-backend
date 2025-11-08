import mongoose from "mongoose";

const jobSchema = new mongoose.Schema({
  status: { type: String, enum: ["pending", "in-progress", "completed"], default: "pending" }
}, { timestamps: true });

const Job = mongoose.model("Job", jobSchema);
export default Job;