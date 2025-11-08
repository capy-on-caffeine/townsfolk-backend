import mongoose from "mongoose";

const feedbackSchema = new mongoose.Schema({
  job: { type: mongoose.Schema.Types.ObjectId, ref: "Job", required: true },
  persona: { type: mongoose.Schema.Types.ObjectId, ref: "Persona", required: true },
  feedback: { type: String, required: true }
}, { timestamps: true });

feedbackSchema.index({ job: 1, persona: 1 }, { unique: true }); // prevents duplicate feedback per persona-job

const Feedback = mongoose.model("Feedback", feedbackSchema);
export default Feedback;  