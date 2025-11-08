import mongoose from "mongoose";

const personaSchema = new mongoose.Schema({
  name: { type: String, required: true },
  age: Number,
  gender: String,
  occupation: String,
  bio: String
}, { timestamps: true });

const Persona = mongoose.model("Persona", personaSchema);
export default Persona;
