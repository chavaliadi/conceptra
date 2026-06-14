from app.models.schemas import (
    Concept,
    ConceptContent,
    Edge,
    Graph,
    QuizQuestion,
    Resource,
    ScheduleItem,
)


def _os_plan_template() -> dict:
    concepts = [
        Concept(id="c1", name="Processes & Threads",
                description="How the OS manages concurrent execution of programs."),
        Concept(id="c2", name="CPU Scheduling",
                description="Algorithms that decide which process runs on the CPU."),
        Concept(id="c3", name="Synchronization",
                description="Mechanisms to coordinate access to shared resources."),
        Concept(id="c4", name="Deadlocks",
                description="Conditions where processes wait forever for each other."),
        Concept(id="c5", name="Memory Management",
                description="How the OS allocates and tracks physical and virtual memory."),
        Concept(id="c6", name="Paging",
                description="Dividing memory into fixed-size pages for efficient allocation."),
        Concept(id="c7", name="Virtual Memory",
                description="Extending available memory using disk as backing store."),
        Concept(id="c8", name="File Systems",
                description="How the OS organizes and persists data on storage devices."),
    ]
    edges = [
        Edge(from_id="c1", to_id="c2"),
        Edge(from_id="c1", to_id="c3"),
        Edge(from_id="c3", to_id="c4"),
        Edge(from_id="c1", to_id="c5"),
        Edge(from_id="c5", to_id="c6"),
        Edge(from_id="c6", to_id="c7"),
        Edge(from_id="c5", to_id="c8"),
    ]
    schedule = [
        ScheduleItem(concept_id="c1", week=1, day=1, priority="high"),
        ScheduleItem(concept_id="c2", week=1, day=2, priority="high"),
        ScheduleItem(concept_id="c3", week=1, day=3, priority="medium"),
        ScheduleItem(concept_id="c4", week=1, day=4, priority="medium"),
        ScheduleItem(concept_id="c5", week=2, day=1, priority="high"),
        ScheduleItem(concept_id="c6", week=2, day=2, priority="high"),
        ScheduleItem(concept_id="c7", week=2, day=3, priority="high"),
        ScheduleItem(concept_id="c8", week=2, day=4, priority="medium"),
    ]
    content = {
        "c1": ConceptContent(
            concept_id="c1",
            explanation=(
                "A **process** is a running program with its own memory space, file descriptors, and state. "
                "A **thread** is a lightweight unit of execution within a process — threads share the process's "
                "memory but have their own stack and registers. The OS scheduler switches between processes and "
                "threads to give the illusion of parallelism on a single CPU."
            ),
            quiz=[
                QuizQuestion(
                    type="mcq",
                    question="What do threads within the same process share?",
                    options=["Stack", "Registers",
                             "Address space", "Program counter"],
                    answer="Address space",
                ),
                QuizQuestion(
                    type="mcq",
                    question="Which component creates the illusion of parallel execution on one CPU?",
                    options=["Compiler", "OS scheduler",
                             "File system", "Cache"],
                    answer="OS scheduler",
                ),
                QuizQuestion(
                    type="short_answer",
                    question="Explain the difference between a process and a thread in one sentence.",
                    answer="A process is an independent program instance with its own resources; a thread is a unit of execution inside a process that shares its memory.",
                ),
            ],
            resources=[
                Resource(type="video", title="Processes vs Threads Explained",
                         url="https://www.youtube.com/watch?v=4rXWV_HA2Tg"),
                Resource(type="docs", title="OS Processes — GeeksforGeeks",
                         url="https://www.geeksforgeeks.org/operating-system-processes/"),
                Resource(type="article", title="Threads and Processes",
                         url="https://en.wikipedia.org/wiki/Thread_(computing)"),
            ],
        ),
        "c6": ConceptContent(
            concept_id="c6",
            explanation=(
                "**Paging** splits physical and virtual memory into fixed-size blocks called pages (typically 4 KB). "
                "The OS maintains a page table mapping virtual pages to physical frames. When a process accesses "
                "a virtual address, the MMU translates it via the page table. Pages not in RAM cause a page fault, "
                "triggering the OS to load them from disk."
            ),
            quiz=[
                QuizQuestion(
                    type="mcq",
                    question="What typically happens on a page fault?",
                    options=[
                        "Process is killed",
                        "OS loads the page from disk",
                        "CPU resets",
                        "File is deleted",
                    ],
                    answer="OS loads the page from disk",
                ),
                QuizQuestion(
                    type="mcq",
                    question="Which hardware unit translates virtual to physical addresses?",
                    options=["MMU", "GPU", "NIC", "DMA controller"],
                    answer="MMU",
                ),
                QuizQuestion(
                    type="short_answer",
                    question="Why does paging reduce external fragmentation?",
                    answer="Fixed-size pages can be placed in any available frame without leaving unusable gaps between allocations.",
                ),
            ],
            resources=[
                Resource(type="video", title="Paging Explained",
                         url="https://www.youtube.com/watch?v=6R3C9ne79kM"),
                Resource(type="docs", title="Paging — OS Notes",
                         url="https://www.geeksforgeeks.org/paging-in-operating-system/"),
                Resource(type="article", title="Virtual Memory and Paging",
                         url="https://en.wikipedia.org/wiki/Paging"),
            ],
        ),
    }
    for concept in concepts:
        if concept.id not in content:
            content[concept.id] = ConceptContent(
                concept_id=concept.id,
                explanation=f"Placeholder explanation for **{concept.name}**. Full content will be generated by the AI pipeline.",
                quiz=[
                    QuizQuestion(
                        type="mcq",
                        question=f"What is {concept.name} primarily about?",
                        options=["Placeholder A", concept.name,
                                 "Placeholder C", "Placeholder D"],
                        answer=concept.name,
                    ),
                ],
                resources=[
                    Resource(
                        type="docs", title=f"Learn {concept.name}", url="https://example.com"),
                ],
            )

    return {
        "topic": "Operating Systems",
        "graph": Graph(concepts=concepts, edges=edges),
        "schedule": schedule,
        "content": content,
    }


def _react_plan_template() -> dict:
    concepts = [
        Concept(id="r1", name="JSX & Components",
                description="Building UI from reusable React components."),
        Concept(id="r2", name="Props & State",
                description="Passing data into components and managing local state."),
        Concept(id="r3", name="useEffect",
                description="Running side effects in functional components."),
        Concept(id="r4", name="Custom Hooks",
                description="Extracting reusable stateful logic into hooks."),
        Concept(id="r5", name="Context API",
                description="Sharing state across the component tree without prop drilling."),
    ]
    edges = [
        Edge(from_id="r1", to_id="r2"),
        Edge(from_id="r2", to_id="r3"),
        Edge(from_id="r3", to_id="r4"),
        Edge(from_id="r2", to_id="r5"),
    ]
    schedule = [
        ScheduleItem(concept_id="r1", week=1, day=1, priority="high"),
        ScheduleItem(concept_id="r2", week=1, day=2, priority="high"),
        ScheduleItem(concept_id="r3", week=1, day=3, priority="medium"),
        ScheduleItem(concept_id="r4", week=1, day=4, priority="medium"),
        ScheduleItem(concept_id="r5", week=1, day=5, priority="low"),
    ]
    content = {
        concept.id: ConceptContent(
            concept_id=concept.id,
            explanation=f"**{concept.name}**: {concept.description} This is fixture content until the AI pipeline generates real explanations.",
            quiz=[
                QuizQuestion(
                    type="mcq",
                    question=f"Which concept covers: {concept.description}?",
                    options=["Vue", concept.name, "Angular", "Svelte"],
                    answer=concept.name,
                ),
            ],
            resources=[
                Resource(type="docs", title="React Docs",
                         url="https://react.dev"),
            ],
        )
        for concept in concepts
    }
    return {
        "topic": "React Fundamentals",
        "graph": Graph(concepts=concepts, edges=edges),
        "schedule": schedule,
        "content": content,
    }


def _python_fundamentals_template() -> dict:
    concepts = [
        Concept(id="p1", name="Data Types & Variables",
                description="Understanding Python's type system and variable scoping."),
        Concept(id="p2", name="Control Flow",
                description="Conditionals (if/else) and loops (for/while) for program logic."),
        Concept(id="p3", name="Functions & Modules",
                description="Defining functions and organizing code into reusable modules."),
        Concept(id="p4", name="Object-Oriented Programming",
                description="Classes, inheritance, and polymorphism in Python."),
        Concept(id="p5", name="File Handling & I/O",
                description="Reading/writing files and handling input/output operations."),
        Concept(id="p6", name="Error Handling",
                description="Try/except blocks and exception management."),
    ]
    edges = [
        Edge(from_id="p1", to_id="p2"),
        Edge(from_id="p2", to_id="p3"),
        Edge(from_id="p3", to_id="p4"),
        Edge(from_id="p3", to_id="p5"),
        Edge(from_id="p2", to_id="p6"),
    ]
    schedule = [
        ScheduleItem(concept_id="p1", week=1, day=1, priority="high"),
        ScheduleItem(concept_id="p2", week=1, day=2, priority="high"),
        ScheduleItem(concept_id="p3", week=1, day=3, priority="high"),
        ScheduleItem(concept_id="p4", week=2, day=1, priority="medium"),
        ScheduleItem(concept_id="p5", week=2, day=2, priority="medium"),
        ScheduleItem(concept_id="p6", week=2, day=3, priority="high"),
    ]
    content = {
        concept.id: ConceptContent(
            concept_id=concept.id,
            explanation=f"**{concept.name}**: {concept.description} Master this fundamental concept to build strong Python programming skills.",
            quiz=[
                QuizQuestion(
                    type="mcq",
                    question=f"What is the primary purpose of {concept.name.lower()}?",
                    options=["Data storage", concept.description,
                             "Memory management", "Network communication"],
                    answer=concept.description,
                ),
            ],
            resources=[
                Resource(type="docs", title="Python Official Docs",
                         url="https://docs.python.org/3/"),
                Resource(type="video", title="Python Tutorial",
                         url="https://www.youtube.com/results?search_query=python+tutorial"),
            ],
        )
        for concept in concepts
    }
    return {
        "topic": "Python Fundamentals",
        "graph": Graph(concepts=concepts, edges=edges),
        "schedule": schedule,
        "content": content,
    }


def _data_structures_template() -> dict:
    concepts = [
        Concept(id="d1", name="Arrays & Lists",
                description="Indexed sequential data storage and manipulation."),
        Concept(id="d2", name="Linked Lists",
                description="Node-based sequential data structures with dynamic sizing."),
        Concept(id="d3", name="Stacks & Queues",
                description="LIFO and FIFO data structures for specialized access patterns."),
        Concept(id="d4", name="Trees & Graphs",
                description="Hierarchical and network data structures for complex relationships."),
        Concept(id="d5", name="Hash Tables",
                description="Key-value pairs with O(1) average lookup time."),
        Concept(id="d6", name="Sorting Algorithms",
                description="Methods to arrange data in order efficiently."),
        Concept(id="d7", name="Searching Algorithms",
                description="Techniques to find elements in data structures."),
    ]
    edges = [
        Edge(from_id="d1", to_id="d3"),
        Edge(from_id="d1", to_id="d6"),
        Edge(from_id="d2", to_id="d3"),
        Edge(from_id="d3", to_id="d4"),
        Edge(from_id="d4", to_id="d5"),
        Edge(from_id="d6", to_id="d7"),
        Edge(from_id="d1", to_id="d7"),
    ]
    schedule = [
        ScheduleItem(concept_id="d1", week=1, day=1, priority="high"),
        ScheduleItem(concept_id="d2", week=1, day=2, priority="medium"),
        ScheduleItem(concept_id="d3", week=1, day=3, priority="high"),
        ScheduleItem(concept_id="d4", week=2, day=1, priority="high"),
        ScheduleItem(concept_id="d5", week=2, day=2, priority="medium"),
        ScheduleItem(concept_id="d6", week=2, day=3, priority="high"),
        ScheduleItem(concept_id="d7", week=3, day=1, priority="high"),
    ]
    content = {
        concept.id: ConceptContent(
            concept_id=concept.id,
            explanation=f"**{concept.name}**: {concept.description} Essential for coding interviews and efficient algorithm design.",
            quiz=[
                QuizQuestion(
                    type="mcq",
                    question=f"What is the key characteristic of {concept.name}?",
                    options=["Slow access", concept.description,
                             "Limited storage", "Single-threaded"],
                    answer=concept.description,
                ),
            ],
            resources=[
                Resource(type="docs", title="Data Structures Guide",
                         url="https://www.geeksforgeeks.org/data-structures/"),
                Resource(type="video", title="Data Structures Course",
                         url="https://www.youtube.com/results?search_query=data+structures+course"),
            ],
        )
        for concept in concepts
    }
    return {
        "topic": "Data Structures",
        "graph": Graph(concepts=concepts, edges=edges),
        "schedule": schedule,
        "content": content,
    }


def _web_development_template() -> dict:
    concepts = [
        Concept(id="w1", name="HTML Basics",
                description="Semantic markup and document structure."),
        Concept(id="w2", name="CSS & Styling",
                description="Visual design and responsive layout techniques."),
        Concept(id="w3", name="JavaScript Fundamentals",
                description="Client-side scripting and DOM manipulation."),
        Concept(id="w4", name="APIs & HTTP",
                description="RESTful principles and web communication protocols."),
        Concept(id="w5", name="Backend Basics",
                description="Server-side logic, databases, and authentication."),
        Concept(id="w6", name="Deployment & DevOps",
                description="Hosting, CI/CD pipelines, and server management."),
    ]
    edges = [
        Edge(from_id="w1", to_id="w2"),
        Edge(from_id="w2", to_id="w3"),
        Edge(from_id="w3", to_id="w4"),
        Edge(from_id="w4", to_id="w5"),
        Edge(from_id="w5", to_id="w6"),
    ]
    schedule = [
        ScheduleItem(concept_id="w1", week=1, day=1, priority="high"),
        ScheduleItem(concept_id="w2", week=1, day=2, priority="high"),
        ScheduleItem(concept_id="w3", week=1, day=3, priority="high"),
        ScheduleItem(concept_id="w4", week=2, day=1, priority="high"),
        ScheduleItem(concept_id="w5", week=2, day=2, priority="medium"),
        ScheduleItem(concept_id="w6", week=3, day=1, priority="low"),
    ]
    content = {
        concept.id: ConceptContent(
            concept_id=concept.id,
            explanation=f"**{concept.name}**: {concept.description} Critical skill for modern web developers.",
            quiz=[
                QuizQuestion(
                    type="mcq",
                    question=f"Why is {concept.name} important in web development?",
                    options=["Legacy reasons", concept.description,
                             "Tradition", "Complexity"],
                    answer=concept.description,
                ),
            ],
            resources=[
                Resource(type="docs", title="MDN Web Docs",
                         url="https://developer.mozilla.org/"),
                Resource(type="video", title="Web Development Tutorial",
                         url="https://www.youtube.com/results?search_query=web+development+course"),
            ],
        )
        for concept in concepts
    }
    return {
        "topic": "Web Development",
        "graph": Graph(concepts=concepts, edges=edges),
        "schedule": schedule,
        "content": content,
    }


TOPIC_FIXTURES: dict[str, dict] = {
    "operating systems": _os_plan_template(),
    "operating system": _os_plan_template(),
    "os": _os_plan_template(),
    "react fundamentals": _react_plan_template(),
    "react": _react_plan_template(),
    "python fundamentals": _python_fundamentals_template(),
    "python": _python_fundamentals_template(),
    "data structures": _data_structures_template(),
    "algorithms": _data_structures_template(),
    "web development": _web_development_template(),
    "web": _web_development_template(),
}

DEFAULT_FIXTURE = _os_plan_template()


def get_fixture_for_topic(topic: str) -> dict:
    normalized = topic.strip().lower()
    for key, fixture in TOPIC_FIXTURES.items():
        if key in normalized or normalized in key:
            return fixture
    return DEFAULT_FIXTURE
