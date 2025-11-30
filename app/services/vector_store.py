"""Vector store service using ChromaDB for semantic email search"""
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from app.core.config import settings


class VectorStoreService:
    """Service for managing email embeddings in ChromaDB"""

    def __init__(self):
        """Initialize ChromaDB client and embedding model"""
        # Connect to ChromaDB
        self.client = chromadb.HttpClient(
            host=settings.CHROMADB_HOST,
            port=settings.CHROMADB_PORT,
            settings=ChromaSettings(
                anonymized_telemetry=False
            )
        )

        # Load embedding model (384 dimensions, fast and efficient)
        self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)

        # Get or create collection for emails
        self.email_collection = self.client.get_or_create_collection(
            name="emails",
            metadata={"description": "Email content embeddings for semantic search"}
        )

        # Get or create collection for user expertise
        self.expertise_collection = self.client.get_or_create_collection(
            name="user_expertise",
            metadata={"description": "User expertise areas based on email patterns"}
        )

    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text

        Args:
            text: Text to embed

        Returns:
            Embedding vector (384 dimensions)
        """
        embedding = self.embedding_model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def add_email(
        self,
        email_id: str,
        subject: str,
        body: str,
        sender: str,
        user_id: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add email to vector store

        Args:
            email_id: Unique email ID
            subject: Email subject
            body: Email body
            sender: Sender email address
            user_id: User ID who received the email
            metadata: Additional metadata

        Returns:
            True if successful
        """
        try:
            # Combine subject and body for embedding
            combined_text = f"{subject}\n\n{body[:2000]}"  # Limit to 2000 chars

            # Generate embedding
            embedding = self._generate_embedding(combined_text)

            # Prepare metadata
            email_metadata = {
                "user_id": str(user_id),
                "sender": sender,
                "subject": subject,
                **(metadata or {})
            }

            # Add to collection
            self.email_collection.add(
                ids=[email_id],
                embeddings=[embedding],
                documents=[combined_text],
                metadatas=[email_metadata]
            )

            return True

        except Exception as e:
            print(f"Error adding email to vector store: {e}")
            return False

    def search_similar_emails(
        self,
        query_text: str,
        user_id: Optional[int] = None,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for similar emails using semantic search

        Args:
            query_text: Query text (can be email content or natural language query)
            user_id: Filter by user ID (None for all users)
            n_results: Number of results to return

        Returns:
            List of similar emails with metadata and similarity scores
        """
        try:
            # Generate query embedding
            query_embedding = self._generate_embedding(query_text)

            # Build filter
            where_filter = {"user_id": str(user_id)} if user_id else None

            # Search
            results = self.email_collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter
            )

            # Format results
            similar_emails = []
            if results and results['ids']:
                for i, email_id in enumerate(results['ids'][0]):
                    similar_emails.append({
                        "email_id": email_id,
                        "distance": results['distances'][0][i],
                        "similarity": 1 - results['distances'][0][i],  # Convert distance to similarity
                        "metadata": results['metadatas'][0][i],
                        "document": results['documents'][0][i]
                    })

            return similar_emails

        except Exception as e:
            print(f"Error searching similar emails: {e}")
            return []

    def find_emails_by_sender(
        self,
        sender: str,
        user_id: int,
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find all emails from a specific sender

        Args:
            sender: Sender email address
            user_id: User ID
            n_results: Maximum number of results

        Returns:
            List of emails from sender
        """
        try:
            results = self.email_collection.get(
                where={
                    "user_id": str(user_id),
                    "sender": sender
                },
                limit=n_results
            )

            emails = []
            if results and results['ids']:
                for i, email_id in enumerate(results['ids']):
                    emails.append({
                        "email_id": email_id,
                        "metadata": results['metadatas'][i],
                        "document": results['documents'][i]
                    })

            return emails

        except Exception as e:
            print(f"Error finding emails by sender: {e}")
            return []

    def add_user_expertise(
        self,
        user_id: int,
        expertise_area: str,
        description: str,
        confidence: float = 1.0
    ) -> bool:
        """
        Add user expertise area to vector store

        Args:
            user_id: User ID
            expertise_area: Expertise area (e.g., "Python development", "Product management")
            description: Detailed description of expertise
            confidence: Confidence score (0.0 to 1.0)

        Returns:
            True if successful
        """
        try:
            # Generate embedding for expertise description
            embedding = self._generate_embedding(description)

            # Create unique ID
            expertise_id = f"user_{user_id}_expertise_{expertise_area.replace(' ', '_')}"

            # Add to collection
            self.expertise_collection.add(
                ids=[expertise_id],
                embeddings=[embedding],
                documents=[description],
                metadatas=[{
                    "user_id": str(user_id),
                    "expertise_area": expertise_area,
                    "confidence": confidence
                }]
            )

            return True

        except Exception as e:
            print(f"Error adding user expertise: {e}")
            return False

    def find_expert_for_topic(
        self,
        topic: str,
        n_results: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find users with expertise matching a topic

        Args:
            topic: Topic or description to match
            n_results: Number of experts to return

        Returns:
            List of matching experts with confidence scores
        """
        try:
            # Generate query embedding
            query_embedding = self._generate_embedding(topic)

            # Search expertise collection
            results = self.expertise_collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )

            # Format results
            experts = []
            if results and results['ids']:
                for i, expertise_id in enumerate(results['ids'][0]):
                    experts.append({
                        "user_id": int(results['metadatas'][0][i]['user_id']),
                        "expertise_area": results['metadatas'][0][i]['expertise_area'],
                        "confidence": results['metadatas'][0][i]['confidence'],
                        "match_score": 1 - results['distances'][0][i],
                        "description": results['documents'][0][i]
                    })

            return experts

        except Exception as e:
            print(f"Error finding expert for topic: {e}")
            return []

    def get_email_context(
        self,
        email_id: str,
        user_id: int,
        n_similar: int = 3
    ) -> Dict[str, Any]:
        """
        Get contextual information for an email

        Args:
            email_id: Email ID
            user_id: User ID
            n_similar: Number of similar emails to retrieve

        Returns:
            Context dict with similar emails and sender history
        """
        try:
            # Get the email
            email = self.email_collection.get(ids=[email_id])

            if not email or not email['documents']:
                return {"similar_emails": [], "sender_emails": []}

            email_text = email['documents'][0]
            sender = email['metadatas'][0].get('sender', '')

            # Find similar emails
            similar = self.search_similar_emails(
                query_text=email_text,
                user_id=user_id,
                n_results=n_similar + 1  # +1 because it will include itself
            )

            # Remove the email itself from results
            similar = [e for e in similar if e['email_id'] != email_id][:n_similar]

            # Find emails from same sender
            sender_emails = self.find_emails_by_sender(
                sender=sender,
                user_id=user_id,
                n_results=5
            )

            # Remove current email from sender history
            sender_emails = [e for e in sender_emails if e['email_id'] != email_id]

            return {
                "similar_emails": similar,
                "sender_emails": sender_emails
            }

        except Exception as e:
            print(f"Error getting email context: {e}")
            return {"similar_emails": [], "sender_emails": []}

    def delete_email(self, email_id: str) -> bool:
        """
        Delete email from vector store

        Args:
            email_id: Email ID to delete

        Returns:
            True if successful
        """
        try:
            self.email_collection.delete(ids=[email_id])
            return True
        except Exception as e:
            print(f"Error deleting email from vector store: {e}")
            return False

    def delete_user_emails(self, user_id: int) -> bool:
        """
        Delete all emails for a user from vector store

        Args:
            user_id: User ID

        Returns:
            True if successful
        """
        try:
            self.email_collection.delete(where={"user_id": str(user_id)})
            self.expertise_collection.delete(where={"user_id": str(user_id)})
            return True
        except Exception as e:
            print(f"Error deleting user emails from vector store: {e}")
            return False


# Global instance
vector_store = VectorStoreService()
