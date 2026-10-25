"""Scenario families: decision templates with deterministic reference rules.

Each family is a first-person decision with two actionable options (plus
``need_more_information``), a set of numeric facts, and two *legitimate* priorities. Each
priority comes with an explicit rule, stated to the user in plain words in the narrative,
that maps the facts to an action through a signed margin: positive margin selects
``positive_action``, negative selects ``negative_action``. Margins are relative distances
to the threshold, so the generator can demand clear (non-borderline) labels.

Families differ in domain, quantities, rule form and wording; they are not numeric copies
of one template. The family is the unit of the dev/holdout split and of bootstrap
resampling.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

Facts = dict[str, float]


def money(v: float) -> str:
    return f"${v:,.0f}"


def pct(v: float) -> str:
    return f"{v:g}%"


def years(v: float) -> str:
    return f"{v:g} years"


def months(v: float) -> str:
    return f"{v:g} months"


def hours(v: float) -> str:
    return f"{v:g} hours"


def minutes(v: float) -> str:
    return f"{v:g} minutes"


@dataclass(frozen=True)
class FactSpec:
    """A numeric input. ``clause`` must contain ``{v}`` and read as a lowercase clause,
    e.g. "the closing costs on the new loan would be {v}"."""

    name: str
    label: str
    unit: str
    lo: float
    hi: float
    step: float
    fmt: Callable[[float], str]
    clause: str
    # Phrase naming a document the user can cite when reporting a corrected value.
    source: str

    def render(self, value: float) -> str:
        return self.clause.format(v=self.fmt(value))

    def sentence(self, value: float) -> str:
        text = self.render(value)
        return text[0].upper() + text[1:] + "."

    def snap(self, value: float) -> float:
        """Round to the fact's grid so rendered numbers look natural."""
        snapped = round(round(value / self.step) * self.step, 6)
        return snapped


@dataclass(frozen=True)
class PrioritySpec:
    id: str
    statement: str
    rule_description: str
    margin: Callable[[Facts], float]
    deciding_fact: str
    required_facts: tuple[str, ...]
    positive_action: str
    negative_action: str

    def action(self, facts: Facts) -> str:
        m = self.margin(facts)
        if m == 0:
            raise ValueError("margin exactly zero: borderline case")
        return self.positive_action if m > 0 else self.negative_action


@dataclass(frozen=True)
class Family:
    id: str
    domain: str
    intro: str
    question: str
    options: dict[str, str]  # code -> option text (verb phrase, capitalised)
    facts: tuple[FactSpec, ...]
    priorities: tuple[PrioritySpec, PrioritySpec]
    irrelevant_details: tuple[str, ...]
    constraints: tuple[Callable[[Facts], bool], ...] = field(default_factory=tuple)

    def fact(self, name: str) -> FactSpec:
        for f in self.facts:
            if f.name == name:
                return f
        raise KeyError(name)

    def priority(self, pid: str) -> PrioritySpec:
        for p in self.priorities:
            if p.id == pid:
                return p
        raise KeyError(pid)

    def other_priority(self, pid: str) -> PrioritySpec:
        return next(p for p in self.priorities if p.id != pid)

    def valid(self, facts: Facts) -> bool:
        return all(c(facts) for c in self.constraints)


def rel(lhs: float, rhs: float) -> float:
    """Signed relative margin of ``lhs`` over ``rhs``."""
    return (lhs - rhs) / abs(rhs)


# --------------------------------------------------------------------------------------
# Family definitions
# --------------------------------------------------------------------------------------

REFINANCE = Family(
    id="refinance",
    domain="housing finance",
    intro="I'm deciding whether to refinance my mortgage.",
    question="Should I refinance my mortgage now?",
    options={
        "refinance": "Refinance the mortgage now",
        "keep_current_loan": "Keep the current mortgage as is",
    },
    facts=(
        FactSpec(
            "closing_costs",
            "closing costs",
            "USD",
            3000,
            9000,
            100,
            money,
            "the closing costs on the new loan would be {v}",
            "the lender's revised estimate",
        ),
        FactSpec(
            "monthly_savings",
            "monthly payment savings",
            "USD/month",
            120,
            450,
            10,
            money,
            "the new loan would lower my monthly payment by {v}",
            "the lender's revised estimate",
        ),
        FactSpec(
            "years_staying",
            "time I plan to stay",
            "years",
            1,
            10,
            0.5,
            years,
            "I expect to stay in this house for about {v}",
            "the relocation letter from my employer",
        ),
        FactSpec(
            "cash_savings",
            "cash savings",
            "USD",
            15000,
            60000,
            500,
            money,
            "I have {v} in cash savings",
            "my latest bank statement",
        ),
        FactSpec(
            "monthly_expenses",
            "monthly expenses",
            "USD/month",
            2500,
            5000,
            100,
            money,
            "my household expenses run about {v} a month",
            "my budgeting app's yearly summary",
        ),
    ),
    priorities=(
        PrioritySpec(
            id="payback",
            statement=(
                "My priority is keeping total housing costs low: refinancing is only worth "
                "it if the monthly savings pay back the closing costs before I move."
            ),
            rule_description="refinance iff 12*years_staying > closing_costs/monthly_savings",
            margin=lambda f: rel(
                12 * f["years_staying"], f["closing_costs"] / f["monthly_savings"]
            ),
            deciding_fact="years_staying",
            required_facts=("closing_costs", "monthly_savings", "years_staying"),
            positive_action="refinance",
            negative_action="keep_current_loan",
        ),
        PrioritySpec(
            id="cushion",
            statement=(
                "My priority is keeping a cash cushion: after paying any upfront costs, my "
                "savings must still cover at least six months of expenses."
            ),
            rule_description="refinance iff cash_savings - closing_costs > 6*monthly_expenses",
            margin=lambda f: rel(f["cash_savings"] - f["closing_costs"], 6 * f["monthly_expenses"]),
            deciding_fact="cash_savings",
            required_facts=("cash_savings", "closing_costs", "monthly_expenses"),
            positive_action="refinance",
            negative_action="keep_current_loan",
        ),
    ),
    irrelevant_details=(
        "the loan officer I spoke with has worked at the bank for eight years.",
        "the house was painted a light grey before we bought it.",
        "the lender's office is about twenty minutes from my work.",
    ),
)

RELOCATION = Family(
    id="relocation",
    domain="career move",
    intro="My employer has offered me a transfer to another city, and I need to decide.",
    question="Should I accept the relocation?",
    options={
        "accept_relocation": "Accept the transfer to the new city",
        "stay_put": "Stay in my current role and city",
    },
    facts=(
        FactSpec(
            "current_salary",
            "current salary",
            "USD/year",
            60000,
            140000,
            1000,
            money,
            "my current salary is {v} a year",
            "my latest pay stub",
        ),
        FactSpec(
            "offer_salary",
            "offered salary",
            "USD/year",
            60000,
            170000,
            1000,
            money,
            "the transfer would pay {v} a year",
            "the written offer from HR",
        ),
        FactSpec(
            "col_increase",
            "cost-of-living increase",
            "percent",
            0,
            30,
            1,
            pct,
            "living costs in the new city are about {v} higher than here",
            "the cost-of-living report HR sent",
        ),
        FactSpec(
            "drive_hours",
            "drive to my parents",
            "hours",
            1,
            10,
            0.5,
            hours,
            "the new city is about {v} by car from my parents",
            "the route planner",
        ),
    ),
    priorities=(
        PrioritySpec(
            id="purchasing_power",
            statement=(
                "My priority is purchasing power: I'll only move if the new salary, "
                "adjusted for the higher living costs, is at least 5% more than I earn now."
            ),
            rule_description="accept iff offer/(1+col/100) > 1.05*current",
            margin=lambda f: rel(
                f["offer_salary"] / (1 + f["col_increase"] / 100), 1.05 * f["current_salary"]
            ),
            deciding_fact="offer_salary",
            required_facts=("offer_salary", "col_increase", "current_salary"),
            positive_action="accept_relocation",
            negative_action="stay_put",
        ),
        PrioritySpec(
            id="near_family",
            statement=(
                "My priority is staying close to my parents: I'll only move if the new city "
                "is within a four-hour drive of them."
            ),
            rule_description="accept iff drive_hours < 4",
            margin=lambda f: rel(4, f["drive_hours"]),
            deciding_fact="drive_hours",
            required_facts=("drive_hours",),
            positive_action="accept_relocation",
            negative_action="stay_put",
        ),
    ),
    irrelevant_details=(
        "the new office building was renovated two years ago.",
        "my manager there would be someone I met once at a conference.",
        "the team in the new city uses the same project-tracking software as mine.",
    ),
)

CERTIFICATION = Family(
    id="certification",
    domain="professional training",
    intro="I'm deciding whether to pay for a professional certification course.",
    question="Should I enroll in the certification course?",
    options={
        "enroll": "Enroll in the certification course",
        "skip_course": "Skip the certification course for now",
    },
    facts=(
        FactSpec(
            "course_cost",
            "course cost",
            "USD",
            2000,
            12000,
            100,
            money,
            "the course costs {v} in total",
            "the program's official fee schedule",
        ),
        FactSpec(
            "raise_per_year",
            "expected raise",
            "USD/year",
            1000,
            8000,
            100,
            money,
            "certified people in my role earn about {v} more per year",
            "my company's published pay bands",
        ),
        FactSpec(
            "years_in_field",
            "time I expect to stay in this field",
            "years",
            1,
            8,
            0.5,
            years,
            "I expect to stay in this field for about {v}",
            "my signed career-plan document",
        ),
        FactSpec(
            "training_budget",
            "reimbursed training budget",
            "USD",
            2000,
            15000,
            100,
            money,
            "my employer reimburses up to {v} of training costs",
            "the HR benefits portal",
        ),
    ),
    priorities=(
        PrioritySpec(
            id="payback",
            statement=(
                "My priority is that the course pays for itself: the raise should cover its "
                "cost within the time I expect to stay in this field."
            ),
            rule_description="enroll iff raise_per_year*years_in_field > course_cost",
            margin=lambda f: rel(f["raise_per_year"] * f["years_in_field"], f["course_cost"]),
            deciding_fact="raise_per_year",
            required_facts=("raise_per_year", "years_in_field", "course_cost"),
            positive_action="enroll",
            negative_action="skip_course",
        ),
        PrioritySpec(
            id="no_out_of_pocket",
            statement=(
                "My priority is not paying out of pocket: I'll only enroll if the course "
                "costs no more than what my employer reimburses."
            ),
            rule_description="enroll iff training_budget > course_cost",
            margin=lambda f: rel(f["training_budget"], f["course_cost"]),
            deciding_fact="training_budget",
            required_facts=("training_budget", "course_cost"),
            positive_action="enroll",
            negative_action="skip_course",
        ),
    ),
    irrelevant_details=(
        "the course is taught in a building with a nice cafeteria.",
        "the exam is offered on weekdays and weekends.",
        "one of my coworkers took a different course last year.",
    ),
)

CAR = Family(
    id="car",
    domain="vehicle finance",
    intro="I need a car and I'm choosing between buying one with a loan and leasing it.",
    question="Should I buy or lease the car?",
    options={
        "buy_car": "Buy the car with the loan offer",
        "lease_car": "Lease the car under the lease offer",
    },
    facts=(
        FactSpec(
            "price",
            "purchase price",
            "USD",
            20000,
            45000,
            500,
            money,
            "the car costs {v} to buy",
            "the dealer's written quote",
        ),
        FactSpec(
            "resale",
            "expected resale value",
            "USD",
            5000,
            25000,
            500,
            money,
            "it should resell for about {v} when I'm done with it",
            "the resale guide the dealer printed",
        ),
        FactSpec(
            "lease_monthly",
            "lease payment",
            "USD/month",
            250,
            650,
            10,
            money,
            "the lease would cost {v} a month",
            "the dealer's written lease quote",
        ),
        FactSpec(
            "years_keep",
            "time I'd keep the car",
            "years",
            2,
            8,
            0.5,
            years,
            "I would drive it for about {v}",
            "my commute plan",
        ),
        FactSpec(
            "loan_monthly",
            "loan payment",
            "USD/month",
            300,
            800,
            10,
            money,
            "the loan payment would be {v} a month",
            "the bank's loan approval letter",
        ),
    ),
    priorities=(
        PrioritySpec(
            id="total_cost",
            statement=(
                "My priority is the lowest total cost over the years I'll drive it: buying "
                "wins only if the price minus the resale value is less than the lease "
                "payments over that time."
            ),
            rule_description="buy iff lease_monthly*12*years_keep > price - resale",
            margin=lambda f: rel(
                f["lease_monthly"] * 12 * f["years_keep"], f["price"] - f["resale"]
            ),
            deciding_fact="lease_monthly",
            required_facts=("lease_monthly", "years_keep", "price", "resale"),
            positive_action="buy_car",
            negative_action="lease_car",
        ),
        PrioritySpec(
            id="low_monthly",
            statement=(
                "My priority is the lowest monthly payment, whatever the total cost; I'll "
                "pick whichever option costs less each month."
            ),
            rule_description="buy iff loan_monthly < lease_monthly",
            margin=lambda f: rel(f["lease_monthly"], f["loan_monthly"]),
            deciding_fact="loan_monthly",
            required_facts=("loan_monthly", "lease_monthly"),
            positive_action="buy_car",
            negative_action="lease_car",
        ),
    ),
    irrelevant_details=(
        "the dealership is open until eight on weekdays.",
        "the car I'm looking at is dark blue.",
        "the salesperson mentioned they also sell motorcycles.",
    ),
    constraints=(lambda f: f["resale"] < 0.8 * f["price"],),
)

FREELANCE = Family(
    id="freelance",
    domain="employment type",
    intro="I'm thinking about leaving my full-time job to work as a freelancer.",
    question="Should I go freelance?",
    options={
        "go_freelance": "Leave the job and go freelance",
        "keep_fulltime_job": "Keep the full-time job for now",
    },
    facts=(
        FactSpec(
            "salary",
            "full-time salary",
            "USD/year",
            60000,
            150000,
            1000,
            money,
            "my full-time salary is {v} a year",
            "my employment contract",
        ),
        FactSpec(
            "hourly_rate",
            "freelance hourly rate",
            "USD/hour",
            40,
            160,
            5,
            money,
            "clients have agreed to pay me {v} an hour",
            "the signed client agreements",
        ),
        FactSpec(
            "billable_hours",
            "billable hours per week",
            "hours/week",
            15,
            40,
            1,
            lambda v: f"{v:g}",
            "I can realistically bill {v} hours a week",
            "my time-tracking records from side projects",
        ),
        FactSpec(
            "benefits_cost",
            "cost of buying my own benefits",
            "USD/year",
            8000,
            25000,
            500,
            money,
            "buying my own health insurance and benefits would cost {v} a year",
            "the insurance marketplace quote",
        ),
        FactSpec(
            "contract_months",
            "signed contract length",
            "months",
            2,
            24,
            1,
            months,
            "my signed client contracts cover the next {v}",
            "the signed client agreements",
        ),
    ),
    priorities=(
        PrioritySpec(
            id="annual_income",
            statement=(
                "My priority is annual income: freelancing is only worth it if 48 weeks of "
                "billable hours, minus the benefits I'd buy myself, beat my salary."
            ),
            rule_description="freelance iff hourly_rate*billable_hours*48 - benefits > salary",
            margin=lambda f: rel(
                f["hourly_rate"] * f["billable_hours"] * 48 - f["benefits_cost"], f["salary"]
            ),
            deciding_fact="hourly_rate",
            required_facts=("hourly_rate", "billable_hours", "benefits_cost", "salary"),
            positive_action="go_freelance",
            negative_action="keep_fulltime_job",
        ),
        PrioritySpec(
            id="income_security",
            statement=(
                "My priority is income security: I'll only leave if signed contracts already "
                "cover at least the next 12 months."
            ),
            rule_description="freelance iff contract_months > 12",
            margin=lambda f: rel(f["contract_months"], 12),
            deciding_fact="contract_months",
            required_facts=("contract_months",),
            positive_action="go_freelance",
            negative_action="keep_fulltime_job",
        ),
    ),
    irrelevant_details=(
        "my home office gets good afternoon light.",
        "my current team is switching to a new chat tool next month.",
        "I prefer to start my workday at nine.",
    ),
)

EXTRA_CASH = Family(
    id="extra_cash",
    domain="debt versus saving",
    intro="I have some extra cash each month and I'm deciding what to do with it.",
    question="Should I put the extra cash toward the loan or invest it?",
    options={
        "pay_down_loan": "Put the extra cash toward the loan",
        "invest_extra_cash": "Save or invest the extra cash instead",
    },
    facts=(
        FactSpec(
            "loan_rate",
            "loan interest rate",
            "percent",
            3,
            12,
            0.25,
            pct,
            "my loan charges {v} interest a year",
            "the loan servicer's statement",
        ),
        FactSpec(
            "expected_return",
            "expected investment return",
            "percent",
            4,
            10,
            0.25,
            pct,
            "I expect my index fund to return about {v} a year",
            "my financial planner's written projection",
        ),
        FactSpec(
            "emergency_fund",
            "emergency fund",
            "USD",
            2000,
            40000,
            500,
            money,
            "I have {v} set aside in an emergency fund",
            "my latest bank statement",
        ),
        FactSpec(
            "monthly_expenses",
            "monthly expenses",
            "USD/month",
            2000,
            6000,
            100,
            money,
            "my essential expenses are about {v} a month",
            "my budgeting app's yearly summary",
        ),
    ),
    priorities=(
        PrioritySpec(
            id="net_worth",
            statement=(
                "My priority is long-run net worth: I'll pay down the loan only if its rate "
                "is higher than the return I expect from investing."
            ),
            rule_description="pay iff loan_rate > expected_return",
            margin=lambda f: rel(f["loan_rate"], f["expected_return"]),
            deciding_fact="loan_rate",
            required_facts=("loan_rate", "expected_return"),
            positive_action="pay_down_loan",
            negative_action="invest_extra_cash",
        ),
        PrioritySpec(
            id="liquidity_first",
            statement=(
                "My priority is having cash for emergencies: I'll only prepay the loan once "
                "my emergency fund covers at least four months of essential expenses."
            ),
            rule_description="pay iff emergency_fund > 4*monthly_expenses",
            margin=lambda f: rel(f["emergency_fund"], 4 * f["monthly_expenses"]),
            deciding_fact="emergency_fund",
            required_facts=("emergency_fund", "monthly_expenses"),
            positive_action="pay_down_loan",
            negative_action="invest_extra_cash",
        ),
    ),
    irrelevant_details=(
        "the loan servicer recently redesigned its website.",
        "my bank branch moved across the street last spring.",
        "I usually check my accounts on Sunday evenings.",
    ),
)

LEASE_RENEWAL = Family(
    id="lease_renewal",
    domain="housing",
    intro="My apartment lease is ending and I'm deciding whether to renew or move.",
    question="Should I renew my lease or move?",
    options={
        "renew_lease": "Renew the lease on my current apartment",
        "move_out": "Move to the other apartment I found",
    },
    facts=(
        FactSpec(
            "renewal_rent",
            "renewal rent",
            "USD/month",
            1400,
            3000,
            25,
            money,
            "renewing would cost {v} a month",
            "the landlord's renewal notice",
        ),
        FactSpec(
            "alt_rent",
            "rent at the other apartment",
            "USD/month",
            1200,
            3000,
            25,
            money,
            "the other apartment rents for {v} a month",
            "the other building's lease offer",
        ),
        FactSpec(
            "moving_cost",
            "moving cost",
            "USD",
            1500,
            5000,
            100,
            money,
            "moving would cost about {v} all in",
            "the movers' written quote",
        ),
        FactSpec(
            "commute_now",
            "current commute",
            "minutes",
            15,
            70,
            5,
            minutes,
            "my commute from here is {v} each way",
            "my commute log",
        ),
        FactSpec(
            "commute_alt",
            "commute from the other apartment",
            "minutes",
            15,
            70,
            5,
            minutes,
            "the commute from the other apartment would be {v} each way",
            "the transit planner",
        ),
    ),
    priorities=(
        PrioritySpec(
            id="save_money",
            statement=(
                "My priority is saving money over the next 12-month lease: moving is only "
                "worth it if a year of rent savings exceeds the cost of moving."
            ),
            rule_description="move iff 12*(renewal_rent - alt_rent) > moving_cost",
            margin=lambda f: rel(12 * (f["renewal_rent"] - f["alt_rent"]), f["moving_cost"]),
            deciding_fact="alt_rent",
            required_facts=("renewal_rent", "alt_rent", "moving_cost"),
            positive_action="move_out",
            negative_action="renew_lease",
        ),
        PrioritySpec(
            id="short_commute",
            statement=(
                "My priority is a shorter commute: I'll move only if the other apartment "
                "cuts my commute, whatever it costs."
            ),
            rule_description="move iff commute_alt < commute_now",
            margin=lambda f: rel(f["commute_now"], f["commute_alt"]),
            deciding_fact="commute_alt",
            required_facts=("commute_now", "commute_alt"),
            positive_action="move_out",
            negative_action="renew_lease",
        ),
    ),
    irrelevant_details=(
        "the other building has a blue front door.",
        "my current landlord's name is Pat.",
        "both buildings get mail delivered around noon.",
    ),
)

STARTUP_OFFER = Family(
    id="startup_offer",
    domain="job choice",
    intro="I have two job offers, one from a startup and one from a large company.",
    question="Which offer should I take?",
    options={
        "join_startup": "Take the offer from the startup",
        "join_large_company": "Take the offer from the large company",
    },
    facts=(
        FactSpec(
            "startup_salary",
            "startup salary",
            "USD/year",
            80000,
            170000,
            1000,
            money,
            "the startup offers a salary of {v} a year",
            "the startup's written offer",
        ),
        FactSpec(
            "bigco_salary",
            "large-company salary",
            "USD/year",
            100000,
            200000,
            1000,
            money,
            "the large company offers {v} a year",
            "the large company's written offer",
        ),
        FactSpec(
            "equity_per_year",
            "expected yearly equity value",
            "USD/year",
            5000,
            80000,
            1000,
            money,
            "the startup equity is worth about {v} a year in expectation",
            "the startup's equity valuation memo",
        ),
        FactSpec(
            "living_costs",
            "annual fixed living costs",
            "USD/year",
            70000,
            150000,
            1000,
            money,
            "our fixed living costs, including the mortgage, are {v} a year",
            "our household budget spreadsheet",
        ),
    ),
    priorities=(
        PrioritySpec(
            id="expected_comp",
            statement=(
                "My priority is expected total compensation: I'll take the startup offer "
                "only if its salary plus the expected yearly equity value beats the large "
                "company's salary."
            ),
            rule_description="startup iff startup_salary + equity_per_year > bigco_salary",
            margin=lambda f: rel(f["startup_salary"] + f["equity_per_year"], f["bigco_salary"]),
            deciding_fact="equity_per_year",
            required_facts=("startup_salary", "equity_per_year", "bigco_salary"),
            positive_action="join_startup",
            negative_action="join_large_company",
        ),
        PrioritySpec(
            id="cover_costs",
            statement=(
                "My priority is covering our fixed costs with guaranteed pay: I'll take the "
                "startup offer only if its salary alone covers our yearly living costs."
            ),
            rule_description="startup iff startup_salary > living_costs",
            margin=lambda f: rel(f["startup_salary"], f["living_costs"]),
            deciding_fact="living_costs",
            required_facts=("startup_salary", "living_costs"),
            positive_action="join_startup",
            negative_action="join_large_company",
        ),
    ),
    irrelevant_details=(
        "the startup's office has a ping-pong table.",
        "the large company's campus has a gym I probably wouldn't use.",
        "both recruiters emailed me on the same Tuesday.",
    ),
)

FAMILIES: dict[str, Family] = {
    f.id: f
    for f in (
        REFINANCE,
        RELOCATION,
        CERTIFICATION,
        CAR,
        FREELANCE,
        EXTRA_CASH,
        LEASE_RENEWAL,
        STARTUP_OFFER,
    )
}

#: Split by family, fixed before any model output exists. Holdout families are never used
#: for prompt or search tuning.
DEV_FAMILIES = ("refinance", "relocation", "certification", "car", "freelance")
HOLDOUT_FAMILIES = ("extra_cash", "lease_renewal", "startup_offer")
